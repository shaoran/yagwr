Installation
============

To install this package::

    pip install yagwr

Usage
=====

After the installation, a script called ``yagwr`` will be available::

    yagwr rules_and_actions.yml


For a complete list of all command line options, please execute::

    yagwr --help


Default host & port
-------------------

By default, ``yagwr`` connects to ``127.0.0.1`` and listens on port ``7777``.
Use the ``--host`` and ``--port`` options to change this values.

SSL support
-----------

``yagwr`` has no native SSL support. It is recommended that you use
`NGINX <https://www.nginx.com/>`_ or `Apache <https://www.apache.org/>`_ and configure
a reverse proxy.

Reverse proxy with ``NGINX``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To setup reverse proxy with ``NGINX``, you need to do the following:

.. code-block:: nginx

    server {
        listen 443 ssl;
        server_name subdomain.domain.tld;

        ssl on;
        ssl_certificate     /etc/letsencrypt/live/subdomain.domain.tld/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/subdomain.domain.tld/privkey.pem;

        access_log  /var/log/nginx/ssl_subdomain.domain.tld-access.log;
        error_log   /var/log/nginx/ssl_subdomain.domain.tld-error.log;

        location / {
            proxy_cache off;
            proxy_pass  http://localhost:7777;
            include /etc/nginx/proxy_params;
            proxy_read_timeout 3600;
        }
    }


.. note::

    On `Debian <http://www.debian.org>`_ based operating systems the file
    ``/etc/nginx/proxy_params`` is usually present. If that's not the case,
    then create this file with this content:

    .. code-block:: nginx

        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;


See also: https://docs.nginx.com/nginx/admin-guide/web-server/reverse-proxy


Reverse proxy with ``Apache``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To setup reverse proxy with ``Apache``, you need to do the following:

.. code-block:: apache

    <VirtualHost *:443>
        ServerName subdomain.domain.tld

        ErrorLog ${APACHE_LOG_DIR}/subdomain.domain.tld-error.log
        CustomLog ${APACHE_LOG_DIR}/subdomain.domain.tld-access.log combined

        SSLEngine on
        SSLCertificateFile      /etc/letsencrypt/live/subdomain.domain.tld/cert.pem
        SSLCertificateKeyFile   /etc/letsencrypt/live/subdomain.domain.tld/privkey.pem
        SSLCertificateChainFile /etc/letsencrypt/live/subdomain.domain.tld/fullchain.pem

        ProxyPreserveHost on
        ProxyPass / http://127.0.0.1:7777/
        ProxyPassReverse / http://127.0.0.1:7777/
    </VirtualHost>


Actions & rules
---------------

``yagwr`` parses a YAML file that contains rules and actions. When Gitlab sends a POST request
to the server, ``yagwr`` goes through the list of rules. If a rule matches the request, then the action
is executed.

Format
~~~~~~

The top level structure of the YAML file is a list with this shape:

.. code-block:: yaml

    ---

    - condition: <COND>
      action: <ACTION>

    - condition: <COND>
      action: <ACTION>

    ...


The file must have at least one condition.


Rules (``<COND>``)
~~~~~~~~~~~~~~~~~~

The following request properties can be checked in the rules:

================ ===================================
Property         Description
================ ===================================
``path``         The request path, e.g. ``/webhook``
``gitlab_token`` Value of the ``X-Gitlab-Token``
                 header
``gitlab_event`` Value of the ``X-Gitlab-Event``
                 header
``gitlab_host``  Hostname of the gitlab instance
                 take makes the request
================ ===================================

The condition can be either

- ``key <OP> value`` where ``key`` is a property as shown in the table
  above and ``<OP>``:

  - ``=``: equals
  - ``!=``: not equals
  - ``~=``: match regular expression
  - ``!~=``: does not match regular expression

- ``any: LIST of conditions``: at least one condition must be true
- ``all: LIST of conditions``: all conditions must be true
- ``not: condition``: negates the condition


Examples
""""""""

- ``X-Gitlab-Event`` *must be 0xdeadbeef*:

  .. code-block:: yaml

      - condition: gitlab_token = 0xdeadeef

- ``X-Gitlab-Event`` *must be 0xdeadbeef and the host must match gitlab[0-9]+.example.com*:

  .. code-block:: yaml

      - condition:
              all:
                  - gitlab_token = 0xdeadbeef
                  - gitlab_host ~= gitlab[0-9]+.example.com

- ``X-Gitlab-Event`` *must be either* Push Hook *or* Tag Push Hook and the host
  must not be invalid.example.com

  .. code-block:: yaml

      - condition:
              all:
                - any:
                    - gitlab_event = Push Hook
                    - gitlab_event = Tag Push Hook
                - not:
                    - gitlab_host = invalid.example.com



Actions (``<ACTION>``)
~~~~~~~~~~~~~~~~~~~~~~

The string passed in the action is executed using `/bin/sh` login shell.

All HTTP-headers sent in the request are exported as environment variables
with the prefix ``YAGWR_`` and white spaces and dashes are replaced by underscores. For example
the value of ``X-Gitlab-Token`` is available as the environment variable
``YAGWR_X_Gitlab_Token``.

The body of the request is piped into the ``stdin`` buffer of the first process defined in the action.

The return code of the action is ignored by ``yagwr``, however it waits for the action to exit before it
continues with the next action.

The action is executed in the same directory where ``yagwr`` is being executed from.


Examples
""""""""

.. code-block:: yaml

    action: /home/project_a/doc/build_docs.py | sendmail status@mycompany.com


Example
-------

.. literalinclude:: examples/config.yml
   :language: yaml
