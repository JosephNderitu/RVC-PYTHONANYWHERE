from django.views.generic import TemplateView

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import LogoutView


from Truck import views
from django.contrib.auth import views as auth_views
from Truck.customer import views as customer_views
from Truck.courier import views as courier_views, apis as courier_apis
from Truck.driver_verification import api as verification_api 
from Truck.goods_classification import api as gc_api


customer_urlpatterns = [
    path('', customer_views.home, name="home"),
    path('profile/', customer_views.profile_page, name="profile"),
    path('payment_method/', customer_views.payment_method_page, name="payment_method"),
    path('create_job/', customer_views.create_job_page, name="create_job"),
    path('jobs/current/', customer_views.current_jobs_page, name="current_jobs"),  # Add trailing slash
    path('jobs/archived/', customer_views.archived_jobs_page, name="archived_jobs"),
    path('jobs/<job_id>/', customer_views.job_page, name="job"),
    path('confirm/<uuid:job_id>/<uuid:token>/', customer_views.confirm_delivery_page, name="confirm_delivery"),
    
    path('api/classify-item/',                gc_api.classify_item,        name='classify_item'),
    path('api/classify-item/status/<job_id>/',gc_api.classify_item_status, name='classify_item_status'),
]

courier_urlpatterns = [
    path('', courier_views.home, name="home"),
    path('jobs/available/', courier_views.available_jobs_page, name="available_jobs"),
    path('jobs/available/<id>/', courier_views.available_job_page, name="available_job"),
    path('jobs/current/', courier_views.current_job_page, name="current_job"),  # Updated this line
    path('jobs/current/<id>/take_photo/', courier_views.current_job_take_photo, name="current_job_take_photo"),  # Corrected the URL pattern
    path('api/jobs/available/', courier_apis.available_jobs_api, name="available_jobs_api"),
    
    path('jobs/complete/', courier_views.job_complete_page, name="job_complete"),
    path('jobs/archived/', courier_views.archived_jobs_page, name="archived_jobs"),
    path('profile/', courier_views.profile_page, name="profile"),
    path('payout_method/', courier_views.payout_method_page, name="payout_method"),
    path('settings/', courier_views.settings_page, name='settings'),
    
    # ── Driver Verification ──────────────────────────────────────────────────
    path('verification/', courier_views.verification_page, name='verification'),
    
    path('api/jobs/current/<id>/update/', courier_apis.current_job_update_api, name="current_job_update_api"),
    path('api/fcm-token/update/', courier_apis.fcm_token_update_api, name="fcm_token_update_api"),
    path('api/jobs/current/json/', courier_apis.current_job_json_api, name="current_job_json_api"),
    
    # ✅ AFTER — proxy registered, browser calls /courier/api/osrm/ → Django → osrm:5000
    path('api/courier-location/update/',       courier_apis.courier_location_update_api, name="courier_location_update_api"),
    path('api/courier-location/<str:job_id>/', courier_apis.courier_location_api,        name="courier_location_api"),
    path('api/osrm/',                          courier_apis.osrm_proxy,                  name="osrm_proxy"),  # ← THIS
    path('api/ors-route/',      courier_apis.ors_route_proxy, name='ors_route_proxy'),
    path('api/traffic-status/', courier_apis.traffic_status,  name='traffic_status'),
    path('api/online-status/', courier_apis.online_status_api, name='online_status_api'),
    
    # ── Verification APIs ────────────────────────────────────────────────────
    path('api/verification/submit/', verification_api.submit_verification_documents, name='verification_submit'),
    # NEW — plain Django view, no DRF auth issues
    path('api/verification/status/', courier_views.verification_status_api, name='verification_status'),
]


urlpatterns = [
    path('admin/', admin.site.urls),
    path('',include('social_django.urls', namespace='social')),
    path('',views.home),
    path('sign_in/',auth_views.LoginView.as_view(template_name = "sign_in.html")),
    path('sign_out/', auth_views.LogoutView.as_view(next_page="/"), name="sign_out"),
    path('sign_out/', views.sign_out, name='sign_out'),
    path('sign_up/', views.sign_up),
    path('customer/', include((customer_urlpatterns,'customer'))),
    path('courier/', include((courier_urlpatterns,'courier'))),  #add the url for
    path('',views.home),
    
    # Password reset paths
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html"), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"), name='password_reset_complete'),
    
    #fire-base messaging url notification push
    path('firebase-messaging-sw.js', TemplateView.as_view(template_name="firebase-messaging-sw.js", content_type="application/javascript")),
    
    # ── PWA ──────────────────────────────────────────────────────────
    path('manifest.json', TemplateView.as_view( template_name='pwa/manifest.json', content_type='application/manifest+json', ), name='pwa_manifest'),
    path('sw.js', TemplateView.as_view( template_name='pwa/sw.js', content_type='application/javascript',),name='pwa_sw'),
    path('offline/',TemplateView.as_view(template_name='pwa/offline.html'),name='pwa_offline'),

    #terms and conditions and billing
    path('terms_and_conditions/', views.terms_and_conditions, name='terms_and_conditions'),
    path('billing/', views.billing, name='billing'),
    path('contact/', views.contact_page, name='contact'),
    
    #dynamically showing success in our work
    path('fetch-stats/', views.fetch_stats, name='fetch_stats'),
    
    #cookies section
    path('set_cookie_expiry/', views.set_cookie_expiry, name='set_cookie_expiry'),
    path('cookie-policy/', views.cookie_policy, name='cookie_policy'),
    
    #quota calculations
    path('get-quote/', views.get_quote_page, name='get_quote'),
    path('api/get-quote/', views.get_quote_api,  name='get_quote_api'),
    path('api/nearest-couriers/', views.nearest_couriers_api,   name='nearest_couriers'),
    path('api/route/', views.public_route_api,      name='public_route'),
    path('api/ors-route/', views.public_ors_route_api,   name='public_ors_route'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

