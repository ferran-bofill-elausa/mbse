FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# Prevent interactive prompts during package installations
ENV DEBIAN_FRONTEND=noninteractive

################################################################################
# Common packages
################################################################################

RUN apt-get update && apt-get install -y \
    curl \
    default-jre-headless \
    graphviz \
    git \
    wget \
    sudo \
    locales \
    python3 \
    python3-pip \
    python3-dev \
    python3-setuptools \
    python-is-python3 \
    xdg-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
    
# Install common Python tooling globally in the devcontainer so it is available
# to the whole workspace without introducing an additional virtual environment
# layer.  --break-system-packages is intentional here because this is a controlled
# development container image rather than a shared host Python installation.
RUN python -m pip install --break-system-packages \
    Jinja2 \
    jsonschema \
    pytest \
    quickjs

# Configure locale (UTF-8)
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

################################################################################
# AI support with OpenCode
################################################################################

# Switch to container user so AI tooling installs in the correct user paths
USER vscode
ENV HOME=/home/vscode

# Install OpenCode
RUN curl -fsSL https://opencode.ai/install | bash

# Create ~/.local/state as vscode so OpenCode has write permissions
RUN mkdir -p /home/vscode/.local/state
