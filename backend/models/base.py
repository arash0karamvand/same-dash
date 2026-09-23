"""Shared model primitives."""

import uuid

from django.db import models
from django.db.models import Q

MONEY_KWARGS = {"max_digits": 18, "decimal_places": 0}
QUANTITY_KWARGS = {"max_digits": 18, "decimal_places": 3}


def rewrite_reference_lookup(model, lookup):
    root, separator, remainder = lookup.partition("__")
    target = getattr(model, "reference_code_fields", {}).get(root)
    if not target:
        return lookup
    return f"{target}_id{separator}{remainder}" if separator else f"{target}_id"


def rewrite_reference_q(model, node):
    if not isinstance(node, Q):
        return node
    clone = Q()
    clone.connector = node.connector
    clone.negated = node.negated
    clone.children = [
        (rewrite_reference_lookup(model, child[0]), child[1])
        if isinstance(child, tuple)
        else rewrite_reference_q(model, child)
        for child in node.children
    ]
    return clone


class ReferenceQuerySet(models.QuerySet):
    def _filter_or_exclude(self, negate, args, kwargs):
        args = tuple(rewrite_reference_q(self.model, arg) for arg in args)
        kwargs = {rewrite_reference_lookup(self.model, key): value for key, value in kwargs.items()}
        return super()._filter_or_exclude(negate, args, kwargs)

    def update(self, **kwargs):
        kwargs = {rewrite_reference_lookup(self.model, key): value for key, value in kwargs.items()}
        return super().update(**kwargs)


class ReferenceManager(models.Manager.from_queryset(ReferenceQuerySet)):
    pass


class ReferenceCodeModel(models.Model):
    """Expose FK-backed reference values through their legacy string attributes."""

    reference_code_fields = {}
    objects = ReferenceManager()

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        values = {
            name: kwargs.pop(name)
            for name in self.reference_code_fields
            if name in kwargs
        }
        super().__init__(*args, **kwargs)
        for name, value in values.items():
            setattr(self, f"{self.reference_code_fields[name]}_id", value)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = {
                self.reference_code_fields.get(field, field) for field in update_fields
            }
        return super().save(*args, **kwargs)

    def reference_code(self, name):
        return getattr(self, f"{self.reference_code_fields[name]}_id")

    def set_reference_code(self, name, value):
        setattr(self, f"{self.reference_code_fields[name]}_id", value)

    def reference_label(self, name):
        obj = getattr(self, self.reference_code_fields[name], None)
        return obj.label if obj else self.reference_code(name)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PublicUUIDModel(models.Model):
    """Stable public identity for cross-module accounting origins."""

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        abstract = True


class AppendOnlyModel(models.Model):
    """Application-level guard for immutable transaction ledgers."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValueError(f"{type(self).__name__} rows are append-only")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError(f"{type(self).__name__} rows are append-only")
