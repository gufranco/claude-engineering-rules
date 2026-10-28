# Docker Dependencies

Applies to any project that runs, builds, or tests through Docker, and to any plan that adds a tool a project needs.

- The image carries every dependency: interpreter, libraries, assemblers, emulators, and test tools, each pinned. The host carries Docker and git, nothing else.
- Every documented command runs through the container. Never tell a user to install Python, a compiler, or any other tool on their machine.
- Never add a native-tool fast path, such as using a tool when it happens to be installed. It makes the host a dependency again.
- A doctor checks the container and Docker's engine, never host tool versions.
- A project that still asks the host for a dependency is out of line: plan the move, and write no new host instructions meanwhile.

Full rule, examples, and rationale: [`standards/docker-dependencies.md`](../standards/docker-dependencies.md). Read it before writing a Dockerfile, install instructions, or a doctor check.

## Provenance

Added 2026-10-28, `single-incident`, by direct user instruction: "Docker deve conter todas as dependencias do projeto, não a máquina host. Temos controle do container, não do host." Origin: a step-by-step install guide told Windows users to install Python on the host, and a proposal let a build use a native assembler when one was installed.
