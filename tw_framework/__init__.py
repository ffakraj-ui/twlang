"""TW Framework package."""

__version__ = "0.9.25"

from .server import run_production_server, SSRCache  # noqa: F401
from .reactivity import (  # noqa: F401
    has_reactivity,
    parse_state_block,
    get_reactivity_runtime_js,
    transform_reactive_attrs,
)
from .compiler import compile_file_pipeline, compile_text_pipeline  # noqa: F401
from .interpreter import Interpreter  # noqa: F401


# ── v0.9.25 New Architecture Modules ────────────────────────────────
# These modules implement Next.js-level features:

# RSC Payload System (React Server Components)
# - RSC binary payload, streaming, "use client"/"use server" directives
try:
    from .rsc_payload import (
        RSCPayload, RSCPayloadBuilder, RSCPayloadStreamer,
        RSCClientRenderer, RSCManifest, RSCMiddleware,
        DirectiveParser, DirectiveInfo,
    )
except ImportError:
    pass

# React Compiler (Automatic Memoization)
# - Analyzes components, auto-inserts useMemo/useCallback
try:
    from .react_compiler import ReactCompiler, HookDependencyOptimizer
except ImportError:
    pass

# React Hooks
# - useOptimistic, useActionState, useFormStatus, useTransition
try:
    from .hooks import (
        useOptimistic, useActionState, useFormStatus, useTransition,
    )
except ImportError:
    pass

# Metadata API
# - OpenGraph, Twitter Cards, JSON-LD, robots, canonical URLs
try:
    from .metadata_api import PageMetadata, MetadataRegistry
except ImportError:
    pass

# Edge Middleware
# - Edge runtime middleware, proxy, request interception
try:
    from .edge_middleware import EdgeMiddleware, EdgeRequest, EdgeResponse
except ImportError:
    pass

# Static Export
# - SPA mode, output:export, generateStaticParams, auto static optimization
try:
    from .static_export import StaticExporter, AutoStaticOptimizer
except ImportError:
    pass

# Custom Image Loader
# - Cloudinary, Imgix, Vercel image optimization
try:
    from .image_loader import ImageLoader, ImageLoaderConfig
except ImportError:
    pass

# Shallow Routing
# - window.history.pushState, URL-based filtering without page reload
try:
    from .shallow_routing import ShallowRouter, ShallowRouteEntry
except ImportError:
    pass


# ── v0.9.25 Next.js 16 Features ─────────────────────────────────────
try:
    from .instant_navigation import InstantNavigationManager, InstantInsights
except ImportError:
    pass
try:
    from .devtools_mcp import DevToolsMCP
except ImportError:
    pass
try:
    from .parallel_routes import ParallelRouteResolver, InterceptingRouteResolver
except ImportError:
    pass
try:
    from .react19_features import ViewTransitionManager, UseEffectEvent, React19Integration
except ImportError:
    pass
try:
    from .web_vitals import WebVitalsOptimizer, StreamingOptimizer
except ImportError:
    pass
try:
    from .enterprise_features import HealthCheckManager, CouplingGraph, ObservabilityManager
except ImportError:
    pass
try:
    from .infrastructure import TerraformGenerator, AWSConfig
except ImportError:
    pass
