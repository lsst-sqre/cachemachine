############
cachemachine
############

Keeping your docker cache fresh!

Cachemachine is a service that runs in a kubernetes cluster that will ensure
certain docker images are pulled to the appropriate nodes in that kubernetes
cluster.

Theory of Operation
===================

Cachemachine presents a standard REST-ful HTTP API with JSON bodies for
individual messages.

Cachemachines are created by POSTing a JSON message to the /cachemachine
endpoint.  The schema is detailed in the src/cachemachine/schemas directory.

In short, each POST creates a resource with a name, a set of kubernetes
labels, and a set of repository managers to determine what images to pull.
The kubernetes labels allow cachemachine to pull different images to certain
portions of the cluster, depending on the labels on each node.  See
`here for more info <https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/>`.

Once the cachemachine is created, it status can be checked by an HTTP GET
to /cachemachine/name.  This will give you details on what images are available,
waiting to be pulled, and generally desired.

While the cachemachine is running, it will continually use the repository managers
to query for the desired list of images to cache.  Each image is pulled by creating
a daemonset (restricted to the labels for the nodes), and waiting for it to start
the images, ensuring they are pulled.  Once all the nodes have pulled the image,
the daemonset is deleted, and the next image is pulled.

Cachemachine offers a helpful URL that says which images are available on all
the nodes for a given set of labels at /cachemachine/name/available.  This is
useful for figuring out what images are already pulled and can be used without
needing to wait for a docker pull.  This will be used by the Nublado service
to help populate the list of images on the spawning screen.

While cachemachines are intended to run forever, they can also be deleted by
sending an HTTP DELETE to /cachemachine/name.

With the ability to create and delete cachemachines through the API, without
a deployment or code change, this makes it easier for even debugging purposes
to make sure a node or a set of nodes has a certain image, at least for a
certain period of time.

Rubin Repository Manager
========================

The list of images to pull is delegated to the RepoMan interface, which takes
the current state of the common image cache on all the nodes, and generates
a list of images to pull.

For the Rubin Observatory, we have a specific tag format with releases, weekly
and daily builds, and a recommended tag that points to what we recommend to run.

This business logic has been tricky since it relates to things like docker tag
formats which can change occasionally.  By having all the business logic in the
RubinRepositoryMan class, we can easily change out that logic while keeping the
rest of the logic the same.

In this business logic, the RubinRepositoryMan class will go reach out to the
docker registry and parse the tags to determine which images to pull.

For times where you just have a static list of images you want to pull, use the
SimpleRepoMan class, which works on a static list that is provided in the pull
request.

Getting Started
===============

To start working on this codebase, make a virtualenv and install the requirements
using the Makefile provided by the safir framework.  You can also use the helper
script iterate.sh to rebuild and redeploy your most recent changes to a minikube
environment.

cachemachine is developed with the `Safir <https://safir.lsst.io>`__ framework.
`Get started with development with the tutorial <https://safir.lsst.io/set-up-from-template.html>`__.
