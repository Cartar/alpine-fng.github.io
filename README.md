# alpine-fng.github.io

## env set up:

```sh
conda env create -f environment.yml
conda activate alpine
```

## Build static website:

```sh
python generate_site.py
```

### test locally:

Navigate to docs and use Python's building in HTTP server to serve the `docs/` directory to port 8000:

```sh
cd docs
python -m http.server 8000
```

Visit http://localhost:8000 in your browser to view the site.

## Uploading new results:
1. Using the `UploadResults` notebook in the data folder, append the latest race data to our DB
2. Re-build the website
3. push!
