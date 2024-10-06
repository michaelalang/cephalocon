# Dashboards 

With the metrics provided by the Flask API, it is possible to create highly detailed dashboards that effectively 
visualize what, when, and where.

![enter image description here](screenshots/clusters-overview.png)

By zooming in on peaks, it becomes clear which entities or users are responsible for generating the majority of 
traffic.

![enter image description here](screenshots/clusters-zoom.png)

By capturing traffic bytes as a metric and consolidating it with bucket-at-rest metrics, leveraging Prometheus 
enables effortless FinOps.

![enter image description here](screenshots/finops-overview.png)

For large-scale deployments, creating per-user detail dashboards is essential to maintaining readability.

![enter image description here](screenshots/user-details-1.png)

![enter image description here](screenshots/user-details-2.png)

# Routing capbilities


Although browsers do not natively provide S3 capabilities for users, Developer Mode offers the ability to 
override the User-Agent, allowing developers to effectively demonstrate Envoy's features.

![enter image description here](screenshots/routing-s3.png)

![enter image description here](screenshots/routing-cluster1.png)

![enter image description here](screenshots/routing-cluster2.png)
