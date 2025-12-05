# TEMPORARILY DISABLED: Phoenix has FastAPI/Pydantic version conflict
# import phoenix as px
import os
from contextlib import contextmanager
# from opentelemetry import trace
# from opentelemetry.sdk.trace import TracerProvider
# from opentelemetry.sdk.trace.export import BatchSpanProcessor
# from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
# from opentelemetry.sdk.resources import Resource

# Global tracer provider
_TRACER_PROVIDER = None

class NoOpSpan:
    """No-op span object that accepts all method calls and does nothing."""
    def set_attribute(self, key, value):
        pass
    def set_attributes(self, attributes):
        pass
    def add_event(self, name, attributes=None):
        pass
    def set_status(self, status):
        pass

class NoOpTracer:
    """No-op tracer that does nothing (used when Phoenix is disabled)."""
    
    @contextmanager
    def start_as_current_span(self, name: str, **kwargs):
        """Context manager that yields a no-op span."""
        yield NoOpSpan()

def init_telemetry(project_name: str = "cognitive-lattice"):
    """
    Initialize Arize Phoenix and OpenTelemetry.
    Launches the Phoenix UI and configures the tracer.
    
    CURRENTLY DISABLED: Phoenix dependency conflict with FastAPI 0.104.1 + Pydantic 2.12.5
    """
    global _TRACER_PROVIDER
    
    print("⚠️  Phoenix telemetry disabled (dependency conflict)")
    print("   System will run without trace visualization")
    return None
    
    # Configure persistence for Phoenix
    # storage_dir = os.path.join(os.getcwd(), "phoenix_storage")
    # os.makedirs(storage_dir, exist_ok=True)
    # os.environ["PHOENIX_WORKING_DIR"] = storage_dir
    
    # # 1. Launch Phoenix (starts the local server and UI)
    # # use_temp_dir=False ensures it uses PHOENIX_WORKING_DIR
    # session = px.launch_app(use_temp_dir=False)
    # print(f"🔥 Arize Phoenix UI launched at: {session.url}")
    # print(f"💾 Phoenix data stored in: {storage_dir}")
    
    # # 2. Configure OpenTelemetry to send traces to Phoenix
    # # Phoenix listens for OTLP/HTTP on port 6006 by default
    # endpoint = "http://127.0.0.1:6006/v1/traces"
    
    # resource = Resource(attributes={
    #     "service.name": project_name,
    # })
    
    # _TRACER_PROVIDER = TracerProvider(resource=resource)
    
    # # Use OTLP Exporter
    # otlp_exporter = OTLPSpanExporter(endpoint=endpoint)
    # span_processor = BatchSpanProcessor(otlp_exporter)
    
    # _TRACER_PROVIDER.add_span_processor(span_processor)
    
    # # Set as global provider (optional, but good practice)
    # trace.set_tracer_provider(_TRACER_PROVIDER)
    
    # return _TRACER_PROVIDER

def get_tracer(name: str):
    """Get a tracer for a specific module (DISABLED - Phoenix conflict)."""
    # Return no-op tracer when Phoenix is disabled
    return NoOpTracer()
