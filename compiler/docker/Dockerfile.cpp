FROM alpine:3.19
RUN apk add --no-cache g++ build-base
RUN adduser -D sandboxuser
USER sandboxuser
WORKDIR /sandbox
