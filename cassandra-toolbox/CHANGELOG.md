# Changelog


## 0.1.5

### cassandra-tracing

#### New Features

- Minimal support has been added for Scylla, which uses a different key structure for columns queried with the `dateOf` operator. This support has been tested with Scylla 1.3 only.

#### Bug Fixes

- Sessions which were skipped due to error were properly recorded, but encountered a bug when their details were printed. Error cases should now have their session ID and error message printed, as intended.


## 0.1.4

- Uploaded to public PyPI
