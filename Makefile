# Scrape tournament data (only available with access to private repo)
scrape:
	python scraper/run.py

# Consolidate raw data into concise .json files
consolidate:
	python -m src.pipeline.run_consolidation

# Enrich data with usefull features
features:
	python -m src.pipeline.run_features

# Train a model on the played matches, predict the outcomes of unplayed matches
model ?= knltb

run-model:
	python -m src.pipeline.run_models $(model)

# Test the functionality of the project (rerun after code refactoring)
test:
	pytest tests/

# Move previous data to the archive, as to not lose previous versions when faulty code is running
archive:
	xcopy data\ data\archive\%date%\ /E /I

# Combined methods for streamlining pipeline workflow
process: consolidate features
pipeline: consolidate features run-model
