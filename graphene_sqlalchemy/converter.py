from graphene import Dynamic, Field, List, String
from sqlalchemy.orm import interfaces

from graphene_sqlalchemy.sqlalchemy_converter import convert_sqlalchemy_type
from graphene_sqlalchemy.fields import ModelField
from .batching import get_batch_resolver
from .fields import BatchSQLAlchemyConnectionField, FilterConnectionField
from .resolvers import get_custom_resolver

try:
    from sqlalchemy_utils import ChoiceType, JSONType, ScalarListType, TSVectorType
except ImportError:
    ChoiceType = JSONType = ScalarListType = TSVectorType = object


def get_column_doc(column):
    return getattr(column, "doc", None)


def is_column_nullable(column):
    return bool(getattr(column, "nullable", True))


def convert_sqlalchemy_relationship(
    relationship_prop,
    obj_type,
    connection_field_factory,
    orm_field_name,
    **field_kwargs,
):
    """
    :param sqlalchemy.RelationshipProperty relationship_prop:
    :param SQLAlchemyObjectType obj_type:
    :param function|None connection_field_factory:
    :param bool batching:
    :param str orm_field_name:
    :param dict field_kwargs:
    :rtype: Dynamic
    """

    def dynamic_type():
        """:rtype: Field|None"""
        direction = relationship_prop.direction
        child_type = obj_type._meta.registry.get_type_for_model(
            relationship_prop.mapper.entity
        )

        if not child_type:
            return None

        if direction == interfaces.MANYTOONE or not relationship_prop.uselist:
            return _convert_o2o_or_m2o_relationship(
                relationship_prop, obj_type, orm_field_name, **field_kwargs
            )

        if direction in (interfaces.ONETOMANY, interfaces.MANYTOMANY):
            return _convert_o2m_or_m2m_relationship(
                relationship_prop,
                obj_type,
                connection_field_factory,
                **field_kwargs,
            )

    return Dynamic(dynamic_type)


def _convert_o2o_or_m2o_relationship(
    relationship_prop, obj_type, orm_field_name, batching=True, **field_kwargs
):
    """
    Convert one-to-one or many-to-one relationshsip. Return an object field.

    :param sqlalchemy.RelationshipProperty relationship_prop:
    :param SQLAlchemyObjectType obj_type:
    :param bool batching:
    :param str orm_field_name:
    :param dict field_kwargs:
    :rtype: Field
    """
    child_type = obj_type._meta.registry.get_type_for_model(
        relationship_prop.mapper.entity
    )

    resolver = get_custom_resolver(obj_type, orm_field_name)
    if resolver is None:
        resolver = get_batch_resolver(relationship_prop, single=True)

    return Field(child_type, resolver=resolver, **field_kwargs)


def _convert_o2m_or_m2m_relationship(
    relationship_prop, obj_type, connection_field_factory, **field_kwargs
):
    """
    Convert one-to-many or many-to-many relationshsip. Return a list field or a connection field.

    :param sqlalchemy.RelationshipProperty relationship_prop:
    :param SQLAlchemyObjectType obj_type:
    :param bool batching:
    :param function|None connection_field_factory:
    :param dict field_kwargs:
    :rtype: Field
    """
    child_type = obj_type._meta.registry.get_type_for_model(
        relationship_prop.mapper.entity
    )

    if not child_type._meta.connection:
        return Field(List(child_type), **field_kwargs)

    # TODO Allow override of connection_field_factory and resolver via ORMField
    if connection_field_factory is None:
        connection_field_factory = BatchSQLAlchemyConnectionField.from_relationship

    return connection_field_factory(
        relationship_prop, obj_type._meta.registry, **field_kwargs
    )


def convert_sqlalchemy_hybrid_method(hybrid_prop, resolver, **field_kwargs):
    if "type_" not in field_kwargs:
        # TODO The default type should be dependent on the type of the property propety.
        field_kwargs["type_"] = String

    return Field(resolver=resolver, **field_kwargs)


def convert_sqlalchemy_composite(composite_prop, registry, resolver):
    converter = registry.get_converter_for_composite(composite_prop.composite_class)
    if not converter:
        try:
            raise Exception(
                "Don't know how to convert the composite field %s (%s)"
                % (composite_prop, composite_prop.composite_class)
            )
        except AttributeError:
            # handle fields that are not attached to a class yet (don't have a parent)
            raise Exception(
                "Don't know how to convert the composite field %r (%s)"
                % (composite_prop, composite_prop.composite_class)
            )

    # TODO Add a way to override composite fields default parameters
    return converter(composite_prop, registry)


def _register_composite_class(cls, registry=None):
    if registry is None:
        from .registry import get_global_registry

        registry = get_global_registry()

    def inner(fn):
        registry.register_composite_converter(cls, fn)

    return inner


convert_sqlalchemy_composite.register = _register_composite_class


def convert_sqlalchemy_column(column_prop, registry, resolver, **field_kwargs):
    column = column_prop.columns[0]
    field_kwargs.setdefault(
        "type_",
        convert_sqlalchemy_type(getattr(column, "type", None), column, registry),
    )
    field_kwargs.setdefault("required", not is_column_nullable(column))
    field_kwargs.setdefault("description", get_column_doc(column))

    return ModelField(resolver=resolver, model_field=column, **field_kwargs)
