FROM docker.io/redhat/ubi9

ADD requirements.txt /opt/app-root/src/requirements.txt 

RUN dnf -y install python3 python3-pip git ; \
    pip3 install -r /opt/app-root/src/requirements.txt ; \
    git clone --depth=1 https://github.com/envoyproxy/envoy.git ; \
    git clone --depth=1 https://github.com/cncf/udpa.git ; \
    git clone --depth=1 https://github.com/bufbuild/protoc-gen-validate.git ; \
    git clone --depth=1 https://github.com/googleapis/googleapis.git ; \
    dnf clean all

RUN python3 -m grpc_tools.protoc -I/envoy/api -I/udpa -I/protoc-gen-validate -I/googleapis -I/envoy/api/envoy/service/auth/v3 \
    --python_out=/opt/app-root --pyi_out=. --grpc_python_out=/opt/app-root /envoy/api/envoy/service/auth/v3/external_auth.proto

ADD ext_auth_grpc_server.py /opt/app-root/ext_auth_grpc_server.py
ADD ratelimiter.py /opt/app-root/ratelimiter.py
ADD rates.py /opt/app-root/rates.py
ADD payment.py /opt/app-root/payment.py
ADD metrics.py /opt/app-root/metrics.py
ADD utils.py /opt/app-root/utils.py
ADD policylimiter.py /opt/app-root/policylimiter.py
ADD policy.py /opt/app-root/policy.py

EXPOSE 9191
WORKDIR /opt/app-root/
ENV PROMETHEUS_MULTIPROC_DIR=/tmp
ENV GRPCPORT=9091
ENTRYPOINT [ "/usr/local/bin/gunicorn" ]
CMD [ "ext_auth_grpc_server:app", "--bind=0.0.0.0:8080" ]
