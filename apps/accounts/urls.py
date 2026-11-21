from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.urls import path, reverse_lazy

from . import views
from .forms import CustomerAuthenticationForm

app_name = 'customer'

urlpatterns = [
    path(
        'iniciar-sesion/',
        LoginView.as_view(
            authentication_form=CustomerAuthenticationForm,
            template_name='registration/login.html',
        ),
        name='login',
    ),
    path('cerrar-sesion/', LogoutView.as_view(next_page='core:home'), name='logout'),
    path('crear-cuenta/', views.register, name='register'),
    path('verificar-email/<str:token>/', views.verify_email, name='verify_email'),
    path('reenviar-verificacion/', views.resend_verification, name='resend_verification'),
    path(
        'restablecer-contrasena/',
        PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            email_template_name='registration/password_reset_email.txt',
            subject_template_name='registration/password_reset_subject.txt',
            success_url=reverse_lazy('customer:password_reset_done'),
        ),
        name='password_reset',
    ),
    path(
        'restablecer-contrasena/enviado/',
        PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'restablecer-contrasena/<uidb64>/<token>/',
        PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url=reverse_lazy('customer:password_reset_complete'),
        ),
        name='password_reset_confirm',
    ),
    path(
        'restablecer-contrasena/completado/',
        PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
        name='password_reset_complete',
    ),
    # Dashboard
    path('mi-area/', views.dashboard, name='dashboard'),
    path('mi-area/archivos/', views.artwork_library, name='artwork_library'),
    path('mi-area/archivos/<int:item_id>/<str:file_kind>/', views.download_customer_file, name='download_customer_file'),

    # Orders
    path('mis-pedidos/', views.order_history, name='order_history'),
    path('mis-pedidos/<str:order_number>/', views.order_detail, name='order_detail'),
    path('mis-pedidos/<str:order_number>/repetir/', views.reorder_order, name='reorder_order'),
    path('mis-pedidos/<str:order_number>/aprobar-prueba/<int:item_id>/', views.approve_proof, name='approve_proof'),
    path('mis-pedidos/<str:order_number>/rechazar-prueba/<int:item_id>/', views.reject_proof, name='reject_proof'),
    path('mis-pedidos/<str:order_number>/subir-arte/<int:item_id>/', views.upload_artwork, name='upload_artwork'),

    # Profile
    path('perfil/', views.ProfileUpdateView.as_view(), name='profile_edit'),

    # Addresses
    path('direcciones/', views.SavedAddressListView.as_view(), name='addresses'),
    path('direcciones/crear/', views.SavedAddressCreateView.as_view(), name='address_create'),
    path('direcciones/<int:pk>/editar/', views.SavedAddressUpdateView.as_view(), name='address_edit'),
    path('direcciones/<int:pk>/eliminar/', views.SavedAddressDeleteView.as_view(), name='address_delete'),
    path('direcciones/<int:pk>/por-defecto/', views.set_default_address, name='set_default_address'),

    # Wishlist
    path('deseos/', views.WishlistListView.as_view(), name='wishlist'),
    path('deseos/anadir/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('deseos/alternar/<int:product_id>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('deseos/eliminar/<int:wishlist_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),

    # Privacy
    path('privacidad/', views.privacy_settings, name='privacy'),
    path('privacidad/exportar/', views.export_customer_data, name='data_export'),
    path('privacidad/eliminar-cuenta/', views.delete_customer_account, name='delete_account'),
]
