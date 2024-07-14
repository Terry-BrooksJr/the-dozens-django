# -*- coding: utf-8 -*-
from API.models import Insult, InsultReview
from django.contrib import admin

all_models = [Insult, InsultReview]
for model in all_models:
    register = admin.site.register(model)
