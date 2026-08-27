from django.urls import include, path
from django.views.generic import TemplateView
from . import views
from .views import ScholarsListView, SuperuserTemplateView

urlpatterns = [
    path('', views.home, name='home'),
    path('healthz/', views.healthz, name='healthz'),
    path('map/', views.map_view, name='map'),
    path('contact/', views.contact, name='contact'),
    path('about/', TemplateView.as_view(template_name='core/about.html'), name='about'),
    path('privacy/', TemplateView.as_view(template_name='core/privacy.html'), name='privacy'),
    path('accessibility/', TemplateView.as_view(template_name='core/accessibility.html'), name='accessibility'),
    path('scholars/', ScholarsListView.as_view(), name='scholars'),

    # Internal admin guides. Superuser-only: they document moderation workflows
    # and are linked from the profile dropdown, not from the public footer.
    path('help/',
         SuperuserTemplateView.as_view(template_name='core/help/index.html'),
         name='help_index'),
    path('help/applications/',
         SuperuserTemplateView.as_view(template_name='core/help/applications.html'),
         name='help_applications'),
    path('help/content/',
         SuperuserTemplateView.as_view(template_name='core/help/content.html'),
         name='help_content'),
    path('publications/', views.publications_list, name='publications'),
    path('api/accounts/search/', views.search_accounts, name='search_accounts'),
    path('api/map/summary/', views.map_summary, name='map_summary'),
    path('api/map/country/<str:code>/', views.map_country_detail, name='map_country_detail'),
]
