# -*- coding: utf-8 -*-
# Generated by Django 4.2.6 on 2023-10-21 21:58

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("API", "0002_alter_insult_last_modified"),
    ]

    operations = [
        migrations.CreateModel(
            name="InsultReview",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("anonymous", models.BooleanField(default=False)),
                (
                    "reporter_first_name",
                    models.CharField(blank=True, max_length=80, null=True),
                ),
                (
                    "reporter_last_name",
                    models.CharField(blank=True, max_length=80, null=True),
                ),
                ("post_review_contact_desired", models.BooleanField(default=False)),
                (
                    "reporter_email",
                    models.EmailField(blank=True, max_length=254, null=True),
                ),
                ("date_submitted", models.DateField(auto_now=True)),
                ("date_reviewed", models.DateField(blank=True, null=True)),
                ("rationale_for_review", models.TextField()),
                (
                    "review_type",
                    models.CharField(
                        choices=[
                            ("RE", "Joke Reclassification"),
                            ("RC", "Joke Recatagorizion"),
                            ("RX", "Joke Removal"),
                        ]
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("P", "Pending"),
                            ("NCE", "Completed - New Explicity Setting"),
                            ("SCE", "Completed - No New Explicity Setting"),
                            ("NJC", "Completed - Assigned to New Catagory"),
                            ("SJC", "Completed - No New Catagory Assigned"),
                            ("X", "Completed - Joke Removed"),
                        ],
                        default="P",
                        null=True,
                    ),
                ),
                (
                    "insult_id",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="API.insult"
                    ),
                ),
            ],
            options={
                "verbose_name": "Joke Needing Review",
                "verbose_name_plural": "Jokes Needing Review",
                "db_table": "reported_jokes",
                "ordering": ["status", "-date_submitted"],
                "get_latest_by": ["-date_submitted"],
            },
        ),
    ]
