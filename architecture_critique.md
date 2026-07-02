architecture critique and ultimate improvements

the current architecture is master on digitalocean, workers on aws ec2. this hybrid cloud thing means extra latency and bandwidth costs. we should just move the master to aws into the same vpc as the workers. 

also, using buildbot means everything is hardcoded in a giant python master.cfg file. if there's a syntax error there (like we had with the unescaped curly braces), the whole ci breaks for everyone. the modern way is declarative ci like github actions or gitlab ci, where the infra team just provides dummy aws runners, and the developers write yaml files in their own repos. it's way more orthogonal.

state management is also bad right now. buildbot uses a local sqlite file. if the digitalocean droplet dies, the ci is dead. if we stick with buildbot, we should use a real database like postgres on aws rds, so we can run multiple masters behind a load balancer for high availability.

finally, building 4gb disk images with mmdebstrap for every tiny code change in zenoh or ros is crazy slow. the long term goal should be to just build a thin base ubuntu image once. then, all the ros2 and robot code should just be packaged as lightweight docker containers (or snaps). when you push code, ci just builds a 50mb docker image in 30 seconds. the robots out in the world just pull the docker container updates over-the-air using something like aws iot greengrass or balena.
