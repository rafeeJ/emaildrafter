from flask import (
	Flask,
	render_template,
	flash,
	jsonify,
	request,
	url_for,
	make_response,
	request,
	redirect,
	abort
)
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, SubmitField
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user, login_required
from wtforms.validators import DataRequired, Length, Email
from mpdetails import validate_postcode_api
from emailtemplates import (
	get_templates_by_topic,
	get_existing_templates,
	draft_templates,
	add_draft_template
)
from users import User, CustomJSONEncoder, add_user, find_user, user_loader_db
from werkzeug.security import generate_password_hash, check_password_hash
from database import myDb
from urllib import parse
from secrets import token_bytes
from address import get_addresses
from bson.objectid import ObjectId
import emailtemplates
import json
import logging
import os
import sys

app = Flask(__name__)
app.logger.addHandler(logging.StreamHandler(sys.stdout))
app.logger.setLevel(logging.DEBUG)

try:
	skey = bytes(os.environ['FLASK_SECRET_KEY'], 'utf-8')

	app.config['RECAPTCHA_PUBLIC_KEY'] = os.environ['RECAPTCHA_PUBLIC_KEY']
	app.config['RECAPTCHA_PRIVATE_KEY'] = os.environ['RECAPTCHA_PRIVATE_KEY']

	enable_recaptcha = True
except KeyError:
	# Testing environment
	skey = token_bytes(16)
	enable_recaptcha = False

app.secret_key = skey

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view='login'

app.json_encoder = CustomJSONEncoder

@app.before_request
def force_https():
	criteria = [
		app.debug,
		request.is_secure,
		request.headers.get("X-Forwarded-Proto", "http") == "https",
	]

	if not any(criteria):
		if request.url.startswith("http://"):
			url = request.url.replace("http://", "https://", 1)
			code = 301
			r = redirect(url, code=code)
			return r

@app.errorhandler(404)
def error_404(error):
	return render_template('404.html', error=error), 404

@app.errorhandler(401)
def error_401(error):
	return render_template('401.html', error=error), 401

# TODO: Write this so it works

@login_manager.user_loader
def user_loader(eid):

	acc = user_loader_db(eid)
	print(acc)
	if acc is not None:
		user = User(acc['_id'], acc['name'], acc['email'], acc['hashed_password'], acc['state'])
		return user


class TemplateSubmissionForm(FlaskForm):
	name = StringField('Your name', validators=[DataRequired(), Length(min=3)])
	email = StringField('Your email address', validators=[DataRequired()], render_kw={'type': 'email'})
	target_name = StringField('Recipient name', validators=[DataRequired(), Length(min=3)])
	target_email = StringField('Recipient email address', validators=[DataRequired()], render_kw={'type': 'email'})
	target_subject = StringField('Email subject', validators=[DataRequired()])
	target_body = TextAreaField('Email template', validators=[DataRequired()], render_kw={'rows':'10'})
	if enable_recaptcha:
		recaptcha = RecaptchaField()

@app.route("/", methods=["GET", "POST"])
def landing():

	if request.method == "GET":
		return render_template("landing.html")
	else:
		name = request.form["name"]
		postcode = request.form["postcode"].replace(" ", "")
		address = request.form.get("address")
		empty_templates = get_existing_templates()
		emails = draft_templates(empty_templates, name, postcode, address)
		return render_template("all-topics.html", emails=emails)


@app.route("/aboutus")
def aboutus():
	return render_template("aboutus.html")


@app.route("/submit-template", methods=["GET", "POST"])
def submit_template():
	form = TemplateSubmissionForm()
	
	if request.method == "POST" and form.validate_on_submit():
		name = form.name.data
		email = form.email.data
		target_name = form.target_name.data
		target_email = form.target_email.data
		target_subject = form.target_subject.data
		target_body = form.target_body.data

		# Do something with the inputs
		# createTemplate(...) --> emails.py:createTemplate(...)
		d = {
		'name' : name,
		'email' : email,
		'target_name' : target_name,
		'target_email' : target_email,
		'subject' : target_subject,
		'body' : target_body
		}

		try:
			add_draft_template(**d)
		except Exception:
			flash('Error when submitting template.', 'danger')

		success = True

		if success:
			return redirect("/success")
	else:
		return render_template("submit-template.html", form=form)

@app.route("/success")
def success():
	return render_template("success.html")


@app.route("/postcode/<postcode>")
def postcode(postcode):
	# ToDo : Re-use this postcode query for MP data gathering
	post_code_data = validate_postcode_api(postcode)
	if post_code_data["status"] == 200:
		return json.dumps(get_addresses(postcode))
	else:
		return make_response({"error": "Invalid postcode"}, 400)


@app.route("/topic/<topic>", methods=["GET", "POST"])
def landing_single_topic(topic):
	matching_templates = get_templates_by_topic(topic)
	if len(matching_templates) == 0:
		abort(404, "Topic not found")
	else:
		if request.method == "GET":
			# ToDo: Need to make a topic-specific landing page
			return render_template("landing.html")
		else:
			name = request.form["name"]
			postcode = request.form["postcode"].replace(" ", "")
			address = request.form.get("address")
			emails = draft_templates(matching_templates, name, postcode, address)
			topic_capitalised = topic.replace("-", " ").title()
			return render_template(
				"single-topic.html", emails=emails, topic=topic_capitalised
			)


@app.route('/register', methods=['GET', 'POST'])
def register():
	if request.method == "POST":
		name=request.form.get("name")
		email=request.form.get("email")
		password=request.form.get("password")

		if len(password) <= 6:
			flash('Password needs to be greater than 6 characters please.', 'danger')
			return render_template('register.html')

		confirm=request.form.get("confirm")
		if password != confirm:
			flash('Please double check your passwords match', 'danger')
			return render_template('register.html')
		hashed_password = generate_password_hash(password)
		add_user(**{"name": name, "email": email, "hashed_password": hashed_password})

		flash('Successfully registered account.', 'success')
	return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'POST':
		email = request.form['email']
		password = request.form['password']
		# Find account and store it in the
		print(repr(email))
		account = find_user(email)
		if account is not None:
			print("Account found, check pswd")
			if check_password_hash(account['hashed_password'], password):
				user = User(account['_id'], account['name'], account['email'] , account['hashed_password'], account['state'])
				print('logging in:',user)
				login_user(user)
				print(user)
				flash('Successful Login', 'success')
			else:
				flash('Incorrect username or password', 'danger')
		else:
			print("account not found")
			flash('Incorrect username or password', 'danger')
	return render_template('login.html')



@app.route('/moderator', methods=['GET', 'POST'])
@login_required
def moderator():
	print(current_user.state, 'MODERATOR')
	if current_user.state == "user":
		abort(401, "User is not a moderator")
	# TODO Return the moderator UI
	return "Hello World"
