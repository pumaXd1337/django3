from django.contrib import admin
from .models import Category, Location, Post


@admin.register(Category, Location, Post)
class AuthorAdmin(admin.ModelAdmin):
    pass
