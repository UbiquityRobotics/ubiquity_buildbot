FROM buildbot/buildbot-master:v2.10.5

COPY requirements.txt /
RUN pip3 install -r /requirements.txt

WORKDIR /var/lib/buildbot

COPY . .

# Setup volumes for building and credentials
VOLUME /buildwork
VOLUME /creds
VOLUME /certs

CMD ["dumb-init", "/usr/src/buildbot/docker/start_buildbot.sh"]

