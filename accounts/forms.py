from django.contrib.auth.forms import PasswordResetForm
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from core.email_utils import send_templated_email

from django import forms
from django.contrib.auth.forms import UserCreationForm as DjangoUserCreationForm
from .models import User


class CustomPasswordResetForm(PasswordResetForm):
    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        subject = render_to_string(subject_template_name, context).strip()
        html_message = render_to_string(email_template_name, context)
        plain_message = strip_tags(html_message)

        print(f"📧 Sending password reset email to {to_email} using Brevo API")

        send_templated_email(
            subject=subject,
            recipients=[to_email],
            template_name=email_template_name,
            context=context,
            text_message=plain_message,
        )
        

from django import forms
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string

User = get_user_model()

from django import forms
from django.utils.crypto import get_random_string

class UserCreationForm(forms.ModelForm):
    """
    Admin form for creating users.

    Username is automatically set to the user's email.
    A temporary password can be manually entered, otherwise
    one is generated automatically.
    """

    temporary_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(
            attrs={
                'placeholder': 'Leave blank to generate automatically',
                'autocomplete': 'new-password',
            }
        ),
        help_text=(
            "Leave blank to generate a secure temporary password automatically."
        )
    )

    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "phone_number",
            "matric_number",
            "gender",
            "is_alumni",
        )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "A user with this email already exists."
            )

        return email

    def save(self, commit=True):
        user = super().save(commit=False)

        # Email is the login identifier.
        email = self.cleaned_data["email"].lower()
        user.email = email
        user.username = email

        # Use manually entered password if supplied.
        temporary_password = self.cleaned_data.get("temporary_password")

        # Otherwise generate one automatically.
        if not temporary_password:
            temporary_password = get_random_string(
                length=12,
                allowed_chars=(
                    "abcdefghijkmnopqrstuvwxyz"
                    "ABCDEFGHJKLMNPQRSTUVWXYZ"
                    "23456789!@#$%"
                )
            )

        user.set_password(temporary_password)

        # Force the user to change the temporary password after login.
        user.must_change_password = True
        user.is_active = True

        if commit:
            user.save()

        # Make password available to the view for the email.
        user._temporary_password = temporary_password

        return user