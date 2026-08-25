FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PORT=8080 PYTHONPATH=/opt/cfre/source
COPY CFRE-OMEGA-RUNTIME-REPAIR-20260825.tar.gz /opt/cfre/CFRE-OMEGA-RUNTIME-REPAIR-20260825.tar.gz
COPY CFRE-OMEGA-RUNTIME-REPAIR-RESPAWN-MANIFEST-20260825.json /opt/cfre/CFRE-OMEGA-RUNTIME-REPAIR-RESPAWN-MANIFEST-20260825.json
RUN echo "58c1e456f02642bcccdf13c8029a07dc4f497f6418c274afc6d8185365f7407b  /opt/cfre/CFRE-OMEGA-RUNTIME-REPAIR-20260825.tar.gz" | sha256sum -c - \
 && echo "c581e04c3a5f15e59451e1fc6201ad1b07032418f632994001bf2d449f6b93e7  /opt/cfre/CFRE-OMEGA-RUNTIME-REPAIR-RESPAWN-MANIFEST-20260825.json" | sha256sum -c - \
 && mkdir -p /opt/cfre/source \
 && tar -xzf /opt/cfre/CFRE-OMEGA-RUNTIME-REPAIR-20260825.tar.gz -C /opt/cfre/source
COPY deployments/cfre_omega_private_runtime/private_runtime.py /app/private_runtime.py
RUN useradd --system --uid 10001 cfre && chown -R cfre:cfre /app
USER cfre
EXPOSE 8080
CMD ["python", "/app/private_runtime.py"]
