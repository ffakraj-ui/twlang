# Getting Started with TW Framework

## Prerequisites

- Python 3.10 or later
- Node.js 18+ (for `.twm` API routes)

## Installation

```bash
pip install tw-framework
```

## Create a New Project

```bash
tw init my-site
cd my-site
```

This creates the following structure:

```
my-site/
├── pages/
│   └── index.tw
├── components/
├── public/
├── tw.config
└── README.md
```

## Development

Start the development server:

```bash
tw dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser. Changes to `.tw`, `.tss`, or `.ts` files will automatically reload the page.

## Build for Production

```bash
tw build
```

The output is placed in the `dist/` directory.

## Deploy

Connect your GitHub repository to Vercel or Netlify. The platform will automatically detect `tw.config` and run `tw build`.

For manual deployment:

```bash
tw deploy --provider vercel --prod
```

## Next Steps

- Read the [language specification](docs/spec/)
- Explore the [deployment guides](docs/deployment/)
- Check the [API reference](docs/api/)
