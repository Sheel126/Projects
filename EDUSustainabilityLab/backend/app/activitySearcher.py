from .models import Activity, Categories, User
from django.db.models import Q, F
from app import activityManager
import json

pillarDict = {
    ""   : "N/A",
    "N/A": "N/A",
    "EN" : "environment",
    "SO" : "social",
    "EC" : "economic"
}

entrepreneurialDict = {
    ""   : "N/A",
    "N/A": "N/A",
    "CU" : "curious",
    "CO" : "connection",
    "CV" : "create"
}

targetDict = {
    ""   : "N/A",
    "N/A": "N/A",
    "EM" : "empathy",
    "DE" : "define",
    "ID" : "ideate",
    "PR" : "prototype",
    "IM" : "implement",
    "AS" : "assess"
}

# Given a search request of categories, output a list of objects that
# maximize those values in descending order
def searchActivitiesWithFilters(request):
    print('req', request)

    name = request.get('name', '').strip()
    pillars = request.get('pillars', [])
    entrepreneurial = request.get('entrepreneurial', [])
    class_sizes = request.get('classSizes', [])
    durations = request.get('durations', [])
    education_levels = request.get('educationLevel', [])
    activity_types = request.get('activityTypes', [])
    activity_disipline = request.get('activityDisipline', [])
    activity_format = request.get('activityFormat', [])

    # Start with approved activities
    queryset = Activity.objects.filter(isApproved=True)

    if name:
        queryset = queryset.filter(title__icontains=name)

    if class_sizes:
        queryset = queryset.filter(classSize__in=class_sizes)

    if durations:
        queryset = queryset.filter(duration__in=durations)

    if education_levels:
        queryset = queryset.filter(levels__in=education_levels)

    if activity_types:
        queryset = queryset.filter(activityType__in=activity_types)  

    if activity_format:
        print('formats', activity_format)
        queryset = queryset.filter(format__in=activity_format)
        
    if activity_disipline:
        queryset = queryset.filter(target__in=activity_disipline)


    if pillars:
        pillar_conditions = Q()

        # Include activities that have non-zero or relevant values for the selected pillars
        if 'Social' in pillars:
            pillar_conditions |= Q(categories__social__gt=0)

        if 'Environment' in pillars:
            pillar_conditions |= Q(categories__environment__gt=0)

        if 'Economic' in pillars:
            pillar_conditions |= Q(categories__economic__gt=0)

        queryset = queryset.filter(pillar_conditions)

    # Entrepreneurial overlap (include if any selected category has value > 0)
    if entrepreneurial:
        entrepreneurial_conditions = Q()

        if 'Curious' in entrepreneurial:
            entrepreneurial_conditions |= Q(categories__curious__gt=0)

        if 'Connection' in entrepreneurial:
            entrepreneurial_conditions |= Q(categories__connection__gt=0)

        if 'Create' in entrepreneurial:
            entrepreneurial_conditions |= Q(categories__create__gt=0)

        queryset = queryset.filter(entrepreneurial_conditions)


    # Sort alphabetically
    queryset = sorted(queryset, key=lambda act: act.title)
    result = [activity.to_dict() for activity in queryset]

    # Sort alphabetically
    queryset = sorted(queryset, key=lambda act: act.title)
    result = [activity.to_dict() for activity in queryset]

    return result



# Return a list of the activities that the user has created
def findAuthoredActivities(author):

    authored_acts = Activity.objects.filter(creator_id=author.id, isApproved=1)
    authored = []

    for activity in authored_acts:
        act = activityManager.getActivity(activity.id)
        authored.append(act.to_dict())

    return authored

# def returnAllApprovedActivities():
#     approvedActivities = Activity.objects.filter(isApproved=True)
#     print('backend all Activities', approvedActivities)
#     activities = []

#     for activity in approvedActivities:
#         act = activityManager.getActivity(activity.id)
#         activities.append(act.to_dict())
#         print(activities[-1])
    
#     return activities

# Method that will handle the search request and delegate the task
# to the apprioate method
# def searchRequest(request):

#     # assume request is a json where the key is where it needs to go

#     if request['Cat'] != None:
#         return searchActivitiesWithFilters(request['Cat'])

#     return 0