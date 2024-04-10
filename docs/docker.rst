.. include:: links.rst


Docker
------

You can learn more about Docker and how to install it in the `Docker installation`_ documentation.
Please make sure you follow the Docker installation instructions. You can check your Docker Runtime installation running their ``hello-world`` image:

.. code-block:: bash

    $ docker run --rm hello-world

If you have a functional installation, then you should obtain the following output:

.. code-block::

    Hello from Docker!
    This message shows that your installation appears to be working correctly.

    To generate this message, Docker took the following steps:
    1. The Docker client contacted the Docker daemon.
    2. The Docker daemon pulled the "hello-world" image from the Docker Hub.
        (amd64)
    3. The Docker daemon created a new container from that image which runs the
        executable that produces the output you are currently reading.
    4. The Docker daemon streamed that output to the Docker client, which sent it
        to your terminal.

    To try something more ambitious, you can run an Ubuntu container with:
    $ docker run -it ubuntu bash

    Share images, automate workflows, and more with a free Docker ID:
    https://hub.docker.com/

    For more examples and ideas, visit:
    https://docs.docker.com/get-started/

After checking your Docker Engine is capable of running Docker images, you are ready to pull your ``m2g`` container image.