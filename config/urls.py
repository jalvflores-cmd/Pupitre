from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

admin.site.site_header = "Pupitre – Administración"
admin.site.site_title = "Pupitre"
admin.site.index_title = "Configuración del establecimiento"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("ingresar/", auth_views.LoginView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("clave/", auth_views.PasswordChangeView.as_view(success_url="/"), name="password_change"),
    path("", include("academico.urls")),
]
