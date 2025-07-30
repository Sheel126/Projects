from django.contrib import admin
from django.urls import path
from . import views as api

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/login/', api.login_view, name='login_view'),
    path('api/logout/', api.logoutUser, name='logoutUser'),
    path('api/register/', api.register_view, name='register_view'),
    path('api/debuggingUser/', api.debuggingUser, name='debuggingUser'),
    path('api/files/', api.fileEndpoint, name='fileEndpoint'),
    path("api/file-info/<int:file_id>/", api.getFileInfo, name="file-info"),
    path('api/files/generate', api.generateImage, name='generateImage'),
    path('api/activities/', api.activityEndpoint, name='activityEndpoint'),
    path('api/pendingUsers/', api.getPendingUsers, name='pendingUsers'),
    path('api/approveUsers/', api.approveUsers, name='approveUsers'),
    path('api/makeAdmin', api.makeAdmin, name='makeAdmin'),
    path('api/download/<int:file_id>/', api.downloadFile, name='downloadFile'),
    path('api/search/', api.searchActivites, name='search'),
    path('api/activity/<int:id>/', api.getActivity),
    path('api/own/', api.getAuthoredActivities),
    path('api/about-content/', api.get_about_content, name='get_about_content'),
    path('api/update-about-content/', api.update_about_content, name='update_about_content'),
    path('api/add-about-section/', api.add_about_section, name='add_about_section'),
    path('api/updateProfile/', api.updateProfile),
    path('api/changePassword/', api.changePassword),
    path('api/approveAll/', api.approveAll),
    path('api/approveActivity/', api.approveActivity),
    path('api/denyActivity/<int:id>/', api.denyActivity)
]
