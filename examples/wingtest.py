#encoding:UTF-8

import wingdbstub
import unittest
import numpy as np
import os

#----------------------------------------------------------------------
def main():
    """"""
    print 'wingide test sucesse!'
    path = os.getcwd()
    print path
    f = open('wingtxttest.txt', 'wb')
    f.write('hello world!')
    f.close()
    
if __name__ == '__main__':
    main()