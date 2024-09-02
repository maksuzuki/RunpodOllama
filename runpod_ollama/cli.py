from typing import Optional
from runpod_ollama import ENVIRONMENT
from runpod_ollama.local_proxy import run_local_proxy
from runpod_ollama.utils import is_port_free
import typer
from rich import print
from rich.console import Console
import runpod  # type: ignore
import inquirer  # type: ignore

err_console = Console(stderr=True, style="bold red")
app = typer.Typer()


try:
    runpod.api_key = ENVIRONMENT.RUNPOD_API_TOKEN
except Exception:
    err_console.print(
        "Runpod API key not found. Please set the RUNPOD_API_KEY environment variable.",
    )
    exit(1)


@app.command()
def create_template(model: str, disk_size: int):
    """Creates a new template for the given model."""

    try:
        response = runpod.create_template(
            name="runpod_ollama",
            image_name="maksuzuki/runpod-ollama:v1",
            docker_start_cmd=model,
            is_serverless=True,
            container_disk_in_gb=disk_size,
        )
        print("Created template:")
        print(response)
        return response
    except Exception as e:
        err_console.print("Failed to create template.")
        err_console.print(e)
        err_console.print("Make sure the template does not already exist.")


def _get_pod_url(
    pod_id: str,
):
    return f"https://www.runpod.io/console/serverless/user/endpoint/{pod_id}"


@app.command()
def create_endpoint(
    name: str,
    template_id: str,
    workers_max: int = 1,
    idle_timeout: int = 60,
):
    """Creates a new endpoint for the given template."""
    # TODO: investigate a way to find the available GPU ids

    try:
        response = runpod.create_endpoint(
            template_id=template_id,
            gpu_ids="NVIDIA RTX A4000",
            name=name,
            workers_max=workers_max,
            idle_timeout=idle_timeout,
            flashboot=True,
        )
        pod_url = _get_pod_url(response["id"])
        print("Created endpoint:")
        print(response)
        print(
            "[bold red]You must manually update the gpu type from 'Edit Endpoint'.[/bold red]"
        )
        print(f"URL: {pod_url}")
        return response
    except Exception as e:
        err_console.print("Failed to create endpoint.")
        err_console.print(e)


@app.command()
def create_model(
    model: str,
    disk_size: int,
    workers_max: int = 1,
    idle_timeout: int = 60,
):
    """Creates a template and endpoint for the given model."""
    template = create_template(model=model, disk_size=disk_size)
    assert template is not None
    endpoint = create_endpoint(
        name=model,
        template_id=template["id"],
        workers_max=workers_max,
        idle_timeout=idle_timeout,
    )
    return endpoint


def _code_example(pod_id: str, model: str):
    return """
```
import litellm

response = litellm.completion(
    "ollama/{model}",
    messages=[
        {{"content": "why the sky is blue?"}},
    ],
    base_url="http://127.0.0.1:5000/{pod_id}",
    stream=False,
)

print(response.choices[0].message["content"]) 
```
    """.format(
        pod_id=pod_id,
        model=model,
    )


@app.command()
def example():
    """Prints an example of how to use the local proxy."""
    endpoints = runpod.get_endpoints()
    endpoint_prompt = inquirer.prompt(
        [
            inquirer.List(
                "endpoint",
                message="Select an endpoint:",
                choices=[e["name"] for e in endpoints],
            )
        ]
    )
    assert endpoint_prompt is not None
    endpoint_name: str = endpoint_prompt["endpoint"]
    endpoint_id = endpoints[
        [endpoint["name"] for endpoint in endpoints].index(endpoint_name)
    ]["id"]

    print(_get_pod_url(endpoint_id))
    print(
        _code_example(
            pod_id=endpoint_id,
            model=endpoint_name,
        )
    )


@app.command()
def start_proxy(debug: Optional[bool] = None):
    """Starts a local proxy to forward requests to the Runpod Ollama service."""
    print(
        "[bold green]Run `runpod-ollama example` to see how to use the proxy.[/bold green]"
    )
    local_proxy_port = 5000
    while not is_port_free(local_proxy_port):
        local_proxy_port += 1
    print(f"Starting local proxy on port {local_proxy_port}")
    run_local_proxy(port=local_proxy_port, debug=debug)


def run_cli():
    app()
