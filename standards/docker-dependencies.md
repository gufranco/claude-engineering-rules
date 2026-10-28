# Docker Dependencies

## Scope

Loaded on demand before writing a Dockerfile, a compose file, install instructions, a build or test entry point, or a doctor check, in any project that uses Docker.

## Core Rule

We control the container and we do not control the host. A dependency in the image is the same version on every machine, every operating system, and CI. A dependency on the host is whatever the user happened to install, and each one is a setup step a user can get wrong. So the image holds everything the project runs, and the host holds only what is needed to fetch the repository and start the image.

## Mandatory Targets

| Item | Where it lives |
|---|---|
| Docker engine | Host |
| git, to clone with submodules | Host |
| Interpreter, such as Python, and its version | Image, pinned |
| Libraries and packages | Image, pinned, from a lockfile |
| Assemblers, compilers, emulators, linters, formatters, coverage | Image, pinned |
| User-supplied artifacts such as ROMs or firmware | Host files, bind-mounted read-only, never baked into the image |

## Install Instructions

Install instructions list Docker and git per operating system, then one command that runs the project in its container. A table of host interpreters, `winget install Python...`, `brew install ...` for a project tool, or a `py -3.12` note is a violation.

## Entry Points

Every documented command, the doctor included, goes through the container: a thin wrapper script, `docker compose run`, or `docker run` with the checkout mounted. A wrapper is a launcher, not a dependency, and is written in what the host already has: a POSIX shell script and a PowerShell script, never a host Python script.

## Doctors

A doctor running inside the container reports the container's tools. The host-side checks are Docker's engine answering, the checkout being a git clone with its submodules, and the bind mounts arriving with content. On macOS with Colima, a mount outside the VM's shared folders arrives empty with no error, so the doctor checks that a known file is visible.

## What Not To Do

- A fast path that uses a tool when the host has it. It is a second, untested configuration, and the host becomes a dependency again.
- Detecting the host interpreter version and advising an upgrade.
- Leaving old host instructions in place while adding container ones. Plan the move and remove the host path in the same change.
