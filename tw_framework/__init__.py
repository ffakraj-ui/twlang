"""TW Framework package."""

__version__ = "0.9.35"

from .server import run_production_server, SSRCache  # noqa: F401
from .reactivity import (  # noqa: F401
    has_reactivity,
    parse_state_block,
    get_reactivity_runtime_js,
    transform_reactive_attrs,
)
from .compiler import compile_file_pipeline, compile_text_pipeline  # noqa: F401
from .interpreter import Interpreter  # noqa: F401


# ── Modules ──
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


# ── Modules ──
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

# ── Modules ──
try:
    from . import adapters
except ImportError:
    pass
try:
    from . import advanced_diagnostics
except ImportError:
    pass
try:
    from . import app_router
except ImportError:
    pass
try:
    from . import asset_optimizer
except ImportError:
    pass
try:
    from . import ast_nodes
except ImportError:
    pass
try:
    from . import build
except ImportError:
    pass
try:
    from . import build_performance
except ImportError:
    pass
try:
    from . import build_report
except ImportError:
    pass
try:
    from . import bundle_optimizer
except ImportError:
    pass
try:
    from . import cache_tiers
except ImportError:
    pass
try:
    from . import cli
except ImportError:
    pass
try:
    from . import client_bundler
except ImportError:
    pass
try:
    from . import code_splitting
except ImportError:
    pass
try:
    from . import common
except ImportError:
    pass
try:
    from . import compiler_stats
except ImportError:
    pass
try:
    from . import component_classifier
except ImportError:
    pass
try:
    from . import csr_mode
except ImportError:
    pass
try:
    from . import dead_code
except ImportError:
    pass
try:
    from . import dependency_graph
except ImportError:
    pass
try:
    from . import deploy
except ImportError:
    pass
try:
    from . import dev
except ImportError:
    pass
try:
    from . import diagnostics
except ImportError:
    pass
try:
    from . import dynamic_imports
except ImportError:
    pass
try:
    from . import edge_db
except ImportError:
    pass
try:
    from . import enhanced_actions
except ImportError:
    pass
try:
    from . import error_boundaries
except ImportError:
    pass
try:
    from . import error_formatter
except ImportError:
    pass
try:
    from . import esbuild_integration
except ImportError:
    pass
try:
    from . import extensions
except ImportError:
    pass
try:
    from . import feature_architecture
except ImportError:
    pass
try:
    from . import fetch_memo
except ImportError:
    pass
try:
    from . import framework
except ImportError:
    pass
try:
    from . import hmr
except ImportError:
    pass
try:
    from . import hydration
except ImportError:
    pass
try:
    from . import icons
except ImportError:
    pass
try:
    from . import image_optimizer
except ImportError:
    pass
try:
    from . import incremental_cache
except ImportError:
    pass
try:
    from . import ir
except ImportError:
    pass
try:
    from . import isr
except ImportError:
    pass
try:
    from . import js_interop
except ImportError:
    pass
try:
    from . import lib_executor
except ImportError:
    pass
try:
    from . import lsp_server
except ImportError:
    pass
try:
    from . import middleware
except ImportError:
    pass
try:
    from . import module_boundaries
except ImportError:
    pass
try:
    from . import npm_manager
except ImportError:
    pass
try:
    from . import parser
except ImportError:
    pass
try:
    from . import partial_rebuild
except ImportError:
    pass
try:
    from . import performance_analyzer
except ImportError:
    pass
try:
    from . import plugin_manager
except ImportError:
    pass
try:
    from . import plugin_runtime
except ImportError:
    pass
try:
    from . import ppr
except ImportError:
    pass
try:
    from . import prefetch
except ImportError:
    pass
try:
    from . import production_optimizer
except ImportError:
    pass
try:
    from . import react_compat
except ImportError:
    pass
try:
    from . import render_css
except ImportError:
    pass
try:
    from . import render_html
except ImportError:
    pass
try:
    from . import route_optimizer
except ImportError:
    pass
try:
    from . import router
except ImportError:
    pass
try:
    from . import runtime_loader
except ImportError:
    pass
try:
    from . import runtime_model
except ImportError:
    pass
try:
    from . import runtime_values
except ImportError:
    pass
try:
    from . import scoped_css
except ImportError:
    pass
try:
    from . import security
except ImportError:
    pass
try:
    from . import semantic
except ImportError:
    pass
try:
    from . import server_actions
except ImportError:
    pass
try:
    from . import static_dynamic_auto
except ImportError:
    pass
try:
    from . import streaming
except ImportError:
    pass
try:
    from . import tailwind_map
except ImportError:
    pass
try:
    from . import tree_shaking
except ImportError:
    pass
try:
    from . import tw_auth
except ImportError:
    pass
try:
    from . import tw_fetch
except ImportError:
    pass
try:
    from . import tw_font
except ImportError:
    pass
try:
    from . import tw_form
except ImportError:
    pass
try:
    from . import tw_image
except ImportError:
    pass
try:
    from . import tw_metadata
except ImportError:
    pass
try:
    from . import tw_realtime
except ImportError:
    pass
try:
    from . import tw_router
except ImportError:
    pass
try:
    from . import tw_runtime
except ImportError:
    pass
try:
    from . import tw_state
except ImportError:
    pass
try:
    from . import twm_parser
except ImportError:
    pass
try:
    from . import websocket
except ImportError:
    pass
