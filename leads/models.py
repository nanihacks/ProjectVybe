from django.db import models

from catalog.models import Project, ProjectAddon, Service


class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CLOSED = "closed", "Closed"

    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="leads",
    )
    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    selected_services = models.ManyToManyField(
        Service,
        blank=True,
        related_name="leads",
        help_text="Choose company services to discuss.",
    )
    selected_addons = models.ManyToManyField(
        ProjectAddon,
        blank=True,
        related_name="leads",
        help_text="Choose project-specific add-ons to discuss.",
    )
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["project", "created_at"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.email}"
