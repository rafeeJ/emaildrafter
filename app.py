from flask import Flask, render_template, flash, jsonify, request
from emails import draftEmails
from urllib import parse
app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def landing():
	if request.method == 'GET':
		return render_template('landing.html')
	else:
		name = request.form['name']
		postcode = request.form['postcode']
		postcode = postcode.replace(" ", "")
		emails = draftEmails(name, postcode)
		a = [{'email': (e.email), 'subject': parse.quote(e.subject), 'body': parse.quote(e.body)} for e in emails]
		# return jsonify(a)
		return render_template('emails.html', emails=a)