# syntax=docker/dockerfile:1
FROM golang:1.27-trixie AS dev
RUN go install github.com/air-verse/air@v1.67.4
WORKDIR /src
COPY go.mod go.sum* ./
RUN go mod download
# source is bind-mounted over /src by docker-compose.override.yml
COPY . .
EXPOSE 8080
CMD ["air", "-c", ".air.toml"]

FROM golang:1.27-trixie AS build
WORKDIR /src
COPY go.mod go.sum* ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/ingest ./cmd/ingest

# distroless: no shell, no package manager; the binary is its own healthcheck client
FROM gcr.io/distroless/static-debian13:nonroot AS prod
COPY --from=build /out/ingest /ingest
EXPOSE 8080
ENTRYPOINT ["/ingest"]
