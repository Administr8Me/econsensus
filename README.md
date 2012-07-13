Consensus decision-making support tool, open source, by Aptivate.

Install Instructions
====================

This is based on using Ubuntu 10.04, but should also work on Debian Squeeze.

First install the requirements:

    $ sudo apt-get install git-core python-virtualenv python-pip sqlite3 \
          python2.6-dev libxml2-dev libyaml-dev mysql-server mysql-client \
          libmysqlclient-dev build-essential libxslt1-dev

Then check out the code:

    $ git clone https://github.com/aptivate/openconsent.git

Then you should be able to do:

    $ cd openconsent
    $ deploy/tasks.py deploy:dev

This should set up the database you need, install the python packages 
required and a few other details. You should now be able to run the 
development server:

    $ cd django/openconsent/
    $ ./manage.py runserver

You should now be able to access the application at:

    http://127.0.0.1:8000/

An initial user ID is created with Username : admin Password : admin
The admin password can be changed through the admin interface at http://127.0.0.1:8000/admin/
User accounts with different privileges can also be created through the admin interface.