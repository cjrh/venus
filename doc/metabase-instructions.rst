Metabase Instructions
---------------------

The easiest way to run metabase is using docker. The insructions are
`here <https://metabase.com/start/docker.html>`_:

.. code-block:: shell

    $ docker run -d -p 3000:3000 --name metabase metabase/metabase

Then visit `http://localhost:3000/`_. During the initial setup for
metabase you will be asked for the location of your database. Imagine
that your Postgresql DB is also running in another docker container, with
port 55432 exposed. When setting up metabase, I could not successfully
connect metabase up to ``localhost:55432``. Instead, I had to use the
address ``host.docker.internal:55432``, which succeeded.

.. image:: /_static/metabase-query.png

.. image:: /_static/metabase-smart-number.png

.. image:: /_static/metabase-line-chart.png
