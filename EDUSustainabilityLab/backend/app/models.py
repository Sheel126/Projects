from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
import json


############################################
#             Constant Values              #
############################################

###  Variables for Lists ###
AGRICULTURE = "AG"
DESIGN = "DI"
EDUCATION = "ED"
ENGINEERING = "EG"
HUMANITIES = "HU"
NATURAL_RESOURCES = "NR"
MANAGEMENT = "MA"
MEDICINE = "MD"
SCIENCE = "SC"
TEXTILES = "TX"
FIRST_YEAR = "FR"
SOPHOMORE = "SO"
JUNIOR = "JR"
SENIOR = "SR"
GRADUATE = "GA"
CONTINUING_EDUCATION = "CE"
MICROMOMENT = "MM"
JIGSAW = "JS"
CASE_STUDY = "CS"
STORYTELLING = "ST"
PROBLEM_BASED = "PB"
SAC = "SC"
EXPERIENTIAL = "EL"
DESIGN_THINKING = "DT"
FIELD_ACTIVITY = "FA"
LAB_COURSE = "LC"
REFLECTION = "RM"
LARGE = "LA"
MEDIUM = "ME"
SMALL = "SM"
SEMESTER = "SE"
WEEK = "WE"
LONG = "LO"
REGULAR = "MD"
SHORT = "SH"
IN_PERSON = "IP"
HYBRID = "HY"
VIRTUAL = "VI"

OTHER = "NA"
EMPTY = "NO"
###########################

TITLE_MAX_LENGTH = 200 #Arbitrary, can be changed
DESCRIPTION_MAX_LENGTH = 1000 #Arbitrary
OBJECTIVE_MAX_LENGTH = 200 #Arbitrary, can be changed

############################################

"""
    Comment Object
"""
class Comment(models.Model):
    commentID = models.BigAutoField(primary_key=True)
    creator = models.IntegerField()
    created = models.DateField(auto_now_add=True)
    description = models.CharField(max_length=500)

"""
    Categories Object
"""
class Categories(models.Model):
    social = models.IntegerField(default=0)
    environment = models.IntegerField(default=0)
    economic = models.IntegerField(default=0)
    create = models.IntegerField(default=0)
    curious = models.IntegerField(default=0)
    connection = models.IntegerField(default=0)
    pillarsObjective = models.TextField(max_length=OBJECTIVE_MAX_LENGTH, blank=True)
    targetEMObjective = models.TextField(max_length=OBJECTIVE_MAX_LENGTH, blank=True)

    def toJSON(self):
        
        return json.dumps(
            self,
            default=lambda o: o.__dict__, 
            sort_keys=True,
            indent=4
        )



"""
    Files Object So we can have a ManyToMany Object in Activity
"""
class File (models.Model):
    file = models.FileField(upload_to='uploads/')

    def get_file_name(self):
        return self.file.name.split('/')[-1] 

    def get_file_extension(self):
        return self.file.name.split('.')[-1].lower()



"""
    Activity Object
"""
class Activity(models.Model):
    
    # The Map of Discplines and their short hand values
    DISCIPLINES = [
        (AGRICULTURE, "Agriculture & Life Science"),
        (DESIGN, "Design"),
        (EDUCATION, "Education"),
        (ENGINEERING, "Engineering"),
        (HUMANITIES, "Humanities & Social Science"),
        (NATURAL_RESOURCES, "Natural Resources"),
        (MANAGEMENT, "Management"),
        (MEDICINE, "Medicine"),
        (SCIENCE, "Science"),
        (TEXTILES, "Textiles"),
        (OTHER, "Other"),
        (EMPTY, "None")
    ]

    # Map of Levels and shorthand values
    LEVELS = [
        (FIRST_YEAR, "First-Year"),
        (SOPHOMORE, "Sophomore"),
        (JUNIOR, "Junior"),
        (SENIOR, "Senior"),
        (GRADUATE, "Graduate"),
        (CONTINUING_EDUCATION, "Continuing Education"),
        (EMPTY, "None")
    ]

    # Map of Activity Types and shorthand values
    ACTIVITY_TYPE = [
        (MICROMOMENT, "Micromoment (e.g., QFT, Think-Pair-Share, etc)"),
        (JIGSAW, "Jigsaw"),
        (CASE_STUDY, "Case Study"),
        (STORYTELLING, "Storytelling"),
        (PROBLEM_BASED, "Problem Solving Studio / Problem-Based Learning"),
        (SAC, "Structured Academic Controversy"),
        (EXPERIENTIAL, "Experiential Learning (hands-on, demonstration)"),
        (DESIGN_THINKING, "Design Thinking"),
        (FIELD_ACTIVITY, "Field Activity"),
        (LAB_COURSE, "Laboratory Course"),
        (REFLECTION, "Reflection / Metacognition"),
        (OTHER, "Other"),
        (EMPTY, "None")
    ]

    # Map of Size and associated int values
    SIZE = [
        (LARGE, "More than 100"),
        (MEDIUM, "50-100"),
        (SMALL, "Less than 50"),
        (EMPTY, "None")
    ]

    # Map of Durations and shorthand values
    DURATION = [
        (SEMESTER, "Semester-Long Project"),
        (WEEK, "Week-Long Project"),
        (LONG, "Long (Over 4 Hours)"),
        (REGULAR, "Medium (Half hour - 4 Hours)"),
        (SHORT, "Short (Half hour or less)"),
        (EMPTY, "None")
    ]

    # Map of Teaching Formats and shorthand values
    FORMATS = [
        (IN_PERSON, "In-Person"),
        (HYBRID, "Hybrid"),
        (VIRTUAL, "Virtual"),
        (EMPTY, "None")
    ]


    # Fields
    # TODO: Figure out default values
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    categories = models.ForeignKey(Categories, on_delete=models.CASCADE)
    title = models.CharField(max_length=TITLE_MAX_LENGTH)
    description = models.TextField(max_length=DESCRIPTION_MAX_LENGTH, blank=True)
    files = models.ManyToManyField(File)     
    tension = models.IntegerField()
    target = models.CharField(max_length=2, choices=DISCIPLINES, default=OTHER)
    levels = models.CharField(max_length=2, choices = LEVELS, default=FIRST_YEAR)
    activityType = models.CharField(max_length=2, choices = ACTIVITY_TYPE, default=OTHER)
    classSize = models.CharField(max_length=2, choices = SIZE, default=LARGE)
    duration = models.CharField(max_length=2, choices = DURATION, default=LONG)
    format = models.CharField(max_length=2, choices = FORMATS, default=IN_PERSON)
    isApproved = models.BooleanField(default=False)
    creationDate = models.DateField(auto_now_add=True)


    def to_dict(self):
        files = list(self.files.all())
        return {
            "id": self.id,
            "creator": self.creator.id,
            "creator_name": self.creator.username,
            "title": self.title,
            "description": self.description,
            "categories": json.loads(self.categories.toJSON()) if hasattr(self.categories, 'toJSON') else {},
            "tension": self.tension,
            "target": self.target,
            "levels": self.levels,
            "activityType": self.activityType,
            "classSize": self.classSize,
            "duration": self.duration,
            "format": self.format,
            "creationDate": str(self.creationDate),
            "isApproved": self.isApproved,
            "file_id": files[0].id if len(files) > 0 else None,
            "image_id": files[1].id if len(files) > 1 else None
        }

    
    def shorthandJSON(self):
        shorthand = {
            "id" : self.id,
            "creator" : self.creator.id,
            "title" : self.title,
            "description" : self.description,
            "categories" : self.categories.toJSON(),
        }

        return json.dumps(shorthand)
    
    def updateStatus(self, status:bool):
        self.isApproved = status


class AboutPageSection(models.Model):
    section_key = models.CharField(max_length=100, unique=True)
    title = models.TextField()
    body = models.TextField()
    order = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.section_key}: {self.title}"