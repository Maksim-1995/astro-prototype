"""Создаёт общий кеш ограничений запросов в PostgreSQL."""

from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    """Создаёт таблицу кеша в базе, к которой применяется миграция."""
    call_command(
        "createcachetable",
        "astro_cache",
        database=schema_editor.connection.alias,
        verbosity=0,
    )


def drop_cache_table(apps, schema_editor):
    """Удаляет таблицу кеша при откате миграции."""
    schema_editor.execute("DROP TABLE IF EXISTS astro_cache")


class Migration(migrations.Migration):
    """Добавляет таблицу кеша после создания основной таблицы заявок."""

    dependencies = [("beta", "0001_initial")]
    operations = [migrations.RunPython(create_cache_table, drop_cache_table)]
