

import wingdbstub
import sys
from random import random
from operator import add

from pyspark.sql import SparkSession
from pyspark import SparkConf, SparkContext


if __name__ == "__main__":
    """
        Usage: pi [partitions]
    """
    conf = SparkConf()
    conf.set("spark.app.name", "example yarn pi")
    conf.set("spark.master", "yarn")
    conf.set("spark.submit.deployMode", "client")
    conf.set("spark.executor.cores", 2)
    conf.set("spark.executor.instances", 16)
    conf.set("spark.locality.wait", "0")
    conf.set("spark.serializer", "org.apache.spark.serializer.KryoSerializer");
    
    spark = SparkContext(conf=conf)

    partitions = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    n = 100000 * partitions

    def f(_):
        x = random() * 2 - 1
        y = random() * 2 - 1
        return 1 if x ** 2 + y ** 2 < 1 else 0

    count = spark.parallelize(range(1, n + 1), partitions).map(f).reduce(add)
    print("Pi is roughly %f" % (4.0 * count / n))

    spark.stop()