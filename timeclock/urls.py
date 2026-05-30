from django.urls import path

from . import views

urlpatterns = [
    # Public — kiosk terminal
    path('', views.punch_terminal, name='punch_terminal'),
    path('api/punch/', views.api_punch, name='api_punch'),

    # Public — employee self-service
    path('meu-ponto/', views.meu_ponto, name='meu_ponto'),
    path('meu-ponto/sair/', views.meu_ponto_sair, name='meu_ponto_sair'),
    path('meu-ponto/abono/', views.meu_ponto_abono, name='meu_ponto_abono'),
    path('api/identify/', views.api_identify, name='api_identify'),

    # Admin panel
    path('painel/dashboard/', views.admin_dashboard, name='admin_dashboard'),

    path('painel/funcionarios/', views.employee_list, name='employee_list'),
    path('painel/funcionarios/novo/', views.employee_create, name='employee_create'),
    path('painel/funcionarios/<int:pk>/editar/', views.employee_edit, name='employee_edit'),
    path('painel/funcionarios/<int:pk>/remover/', views.employee_delete, name='employee_delete'),

    path('painel/batidas/', views.punch_list, name='punch_list'),
    path('painel/batidas/nova/', views.punch_create, name='punch_create'),
    path('painel/batidas/<int:pk>/editar/', views.punch_edit, name='punch_edit'),
    path('painel/batidas/<int:pk>/remover/', views.punch_delete, name='punch_delete'),

    path('painel/abonos/', views.absence_list, name='absence_list'),
    path('painel/abonos/novo/', views.absence_create, name='absence_create'),
    path('painel/abonos/<int:pk>/aprovar/', views.absence_approve, name='absence_approve'),
    path('painel/abonos/<int:pk>/remover/', views.absence_delete, name='absence_delete'),

    path('painel/saldo/', views.balance_view, name='balance_view'),

    path('painel/relatorios/', views.reports_view, name='reports_view'),
    path('painel/relatorios/pdf/', views.report_pdf, name='report_pdf'),
    path('painel/relatorios/email/', views.report_send_email, name='report_send_email'),
]
