# group-communication
A reliable causal total group multicast message delivery API for multiple
processes to communicate in a closed group.

Step 1 implements how a process can enter or leave a group, while the service notifies the other group members.
Step 2 implements the communication of the processes in the group, sending and receiving messages using UDP multicast to reduce the number of transmissions compared with end-to-end communication. 