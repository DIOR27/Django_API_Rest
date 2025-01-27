from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet,
    add_preferences,
    callback,
    get_user_info
)

user_router = DefaultRouter()
user_router.register("users", UserViewSet)

urlpatterns = [
    path(
        "users/add-preferences/<int:user_id>/<str:track>/<str:artist>/",
        add_preferences,
        name="add_preferences",
    ),
    path("callback/", callback, name="callback"),
    path("users/get-user-info/", get_user_info, name="get_user_info"),
]

urlpatterns += user_router.urls
