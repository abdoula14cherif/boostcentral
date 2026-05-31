import re
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, IntegerField, HiddenField, BooleanField, FloatField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange, Optional, ValidationError, Regexp

def validate_password_strength(form, field):
    password = field.data
    errors = []
    if len(password) < 8:
        errors.append("au moins 8 caracteres")
    if not re.search(r"[A-Z]", password):
        errors.append("une majuscule")
    if not re.search(r"[0-9]", password):
        errors.append("un chiffre")
    if errors:
        raise ValidationError(f"Le mot de passe doit contenir : {', '.join(errors)}.")

class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Mot de passe", validators=[DataRequired(), Length(min=1, max=128)])

class RegisterForm(FlaskForm):
    full_name = StringField("Nom", validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    country = StringField("Pays", validators=[Optional(), Length(max=100)])
    password = PasswordField("Mot de passe", validators=[DataRequired(), validate_password_strength])
    confirm_password = PasswordField("Confirmer", validators=[DataRequired(), EqualTo("password", message="Les mots de passe ne correspondent pas.")])

class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])

class OrderForm(FlaskForm):
    network = SelectField("Reseau", choices=[], validators=[DataRequired()])
    service_id = SelectField("Service", choices=[], coerce=int, validators=[DataRequired()])
    link = StringField("Lien", validators=[DataRequired(), Length(max=500)])
    quantity = IntegerField("Quantite", validators=[DataRequired(), NumberRange(min=1)])

class RechargeMMForm(FlaskForm):
    amount = FloatField("Montant", validators=[DataRequired(), NumberRange(min=500)])
    phone_number = StringField("Numero", validators=[DataRequired(), Length(min=8, max=15)])
    method = HiddenField(validators=[DataRequired()])

class RechargeCryptoForm(FlaskForm):
    amount = FloatField("Montant", validators=[DataRequired(), NumberRange(min=1000)])
    txid = StringField("TXID", validators=[DataRequired(), Length(min=10, max=200)])
    method = HiddenField(validators=[DataRequired()])

class AdminOrderUpdateForm(FlaskForm):
    order_id = HiddenField(validators=[DataRequired()])
    status = SelectField("Statut", choices=[("en_attente","En attente"),("en_cours","En cours"),("termine","Termine"),("refuse","Refuse")], validators=[DataRequired()])
    progression = IntegerField("Progression", validators=[NumberRange(min=0, max=100)], default=0)
    admin_note = StringField("Note", validators=[Optional(), Length(max=500)])

class AdminRechargeForm(FlaskForm):
    recharge_id = HiddenField(validators=[DataRequired()])
    action = SelectField("Action", choices=[("valider","Valider"),("refuser","Refuser")], validators=[DataRequired()])
    admin_note = StringField("Note", validators=[Optional(), Length(max=500)])

class AdminServiceForm(FlaskForm):
    service_id = HiddenField(validators=[DataRequired()])
    prix_fcfa = FloatField("Prix", validators=[DataRequired(), NumberRange(min=0.1)])
    min_qte = IntegerField("Min", validators=[DataRequired(), NumberRange(min=1)])
    max_qte = IntegerField("Max", validators=[DataRequired(), NumberRange(min=1)])
    description = StringField("Description", validators=[Optional(), Length(max=500)])
    actif = BooleanField("Actif")

class AdminBalanceForm(FlaskForm):
    user_id = HiddenField(validators=[DataRequired()])
    new_balance = FloatField("Solde", validators=[DataRequired(), NumberRange(min=0)])
