#!/usr/bin/env python

# LSST Data Management System
# Copyright 2013-2014 LSST Corporation.
# 
# This product includes software developed by the
# LSST Project (http://www.lsst.org/).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the LSST License Statement and 
# the GNU General Public License along with this program.  If not, 
# see <http://www.lsstcorp.org/LegalNotices/>.

"""
This is a unittest for the Db class, geared for testing local server connections.
It is assumed user has all privileges.

It requires ~/.lsst.testLocal.my.cnf config file with the following:
[client]
user     = <username>
password = <password> # this can be ommitted if password is empty
host     = localhost
port     = <port>
socket   = <socket>

@author  Jacek Becla, SLAC

Known issues and todos:
 * restarting server test - it'd be best to restart it for real (without blocking
   on user input.
"""

import ConfigParser
import logging
import os
import tempfile
import time
import unittest
from lsst.db.db import Db, DbException

class TestDbLocal(unittest.TestCase):
    def setUp(self):
        self._credFile = "~/.lsst.testLocal.my.cnf"
        self._initCredentials()
        self._dbA = "%s_dbWrapperTestDb_A" % self._user
        self._dbB = "%s_dbWrapperTestDb_B" % self._user
        self._dbC = "%s_dbWrapperTestDb_C" % self._user

        db = Db(self._user, self._pass, self._host, self._port, self._sock)
        if db.dbExists(self._dbA): db.dropDb(self._dbA)
        if db.dbExists(self._dbB): db.dropDb(self._dbB)
        if db.dbExists(self._dbC): db.dropDb(self._dbC)
        db.disconnect()

    def _initCredentials(self):
        if self._credFile.startswith('~'): 
            self._credFile = os.path.expanduser(self._credFile)
        if not os.path.isfile(self._credFile):
            raise Exception("Required file '%s' not found" % self._credFile)
        cnf = ConfigParser.ConfigParser()
        cnf.read(self._credFile)
        if not cnf.has_section("client"):
            raise Exception("Missing section 'client' in '%s'" % self._credFile)
        for o in ("socket", "host", "port", "user"):
            if not cnf.has_option("client", o):
                raise Exception("Missing option '%s' in '%s'" % (o,self._credFile))
        self._sock = cnf.get("client", "socket")
        self._host = cnf.get("client", "host")
        self._port = cnf.get("client", "port")
        self._user = cnf.get("client", "user")
        if cnf.has_option("client", "password"):
            self._pass = cnf.get("client", "password")
        else:
            self._pass = ''

    def testBasicHostPortConn(self):
        """
        Basic test: connect through port, create db and connect to it, create one
        table, drop the db, disconnect.
        """
        db = Db(self._user, self._pass, self._host, self._port)
        db.createDb(self._dbA)
        db.useDb(self._dbA)
        db.createTable("t1", "(i int)")
        db.dropDb(self._dbA)
        db.disconnect()

    def testBasicSocketConn(self):
        """
        Basic test: connect through socket, create db and connect to it, create one
        table, drop the db, disconnect.
        """
        db = Db(self._user, self._pass, socket=self._sock)
        db.createDb(self._dbA)
        db.useDb(self._dbA)
        db.createTable("t1", "(i int)")
        db.dropDb(self._dbA)
        db.disconnect()

    def testBasicOptionFileConn(self):
        db = Db(optionFile=self._credFile)
        db.createDb(self._dbA)
        db.dropDb(self._dbA)
        db.disconnect()

    def testUseDb(self):
        db = Db(self._user, self._pass, socket=self._sock)
        db.createDb(self._dbA)
        db.useDb(self._dbA)
        db.createTable("t1", "(i int)")
        self.assertRaises(DbException, db.useDb, "invDbName")
        db.dropDb(self._dbA)
        self.assertRaises(DbException, db.createTable, "t1", "(i int)")
        db.createDb(self._dbB)
        db.useDb(self._dbB)
        db.createTable("t1", "(i int)")
        db.dropDb(self._dbB)

    def testConn_invalidHost(self):
        db = Db(self._user, self._pass, "invalidHost", self._port)
        self.assertRaises(DbException, db.connect)

    def testConn_invalidHost(self):
        db = Db(self._user, self._pass, "dummyHost", 3036)
        self.assertRaises(DbException, db.connect)

    def testConn_invalidPortNo(self):
        self.assertRaises(DbException, Db, self._user, self._pass,self._host,987654)

    def testConn_wrongPortNo(self):
        db = Db(self._user, self._pass, self._host, 1579, 
                sleepLen=0, maxRetryCount=10)
        self.assertRaises(DbException, db.connect)

    def testConn_invalidUserName(self):
        db = Db("hackr", self._pass, self._host, self._port)
        # Disabling because this can work, depending on MySQL 
        # configuration, for example, it can default to ''@localhost
        # self.assertRaises(DbException, db.connect)
        db = Db(self._user, "!MyPw", self._host, self._port)
        # self.assertRaises(DbException, db.connect)

    def testConn_invalidSocket(self):
        # make sure retry is disabled, otherwise it wil try to reconnect 
        # (it will assume the server is down and socket valid).
        db = Db(self._user, self._pass, socket="/x/sock", maxRetryCount=0)
        self.assertRaises(DbException, db.connect)

    def testConn_badHostPortGoodSocket(self):
        # invalid host, but good socket
        db = Db(self._user, self._pass, "invalidHost", self._port, self._sock)
        db.connect()
        db.disconnect()
        # invalid port but good socket
        db = Db(self._user, self._pass, self._host, 9876543, self._sock)
        db.connect()
        db.disconnect()

    def testConn_badSocketGoodHostPort(self):
        # invalid socket, but good host/port
        # note, it will try to use socket and will NOT fall back to host/port
        db = Db(self._user, self._pass, self._host, self._port, "/x/sock")
        self.assertRaises(DbException, db.connect)
        db.disconnect()

    def testConn_invalidOptionFile(self):
        try:
            db = Db(optionFile="/tmp/dummy.opt.file.xyz")
        except DbException:
            pass

    def testConn_badOptionFile(self):
        # start with an empty file
        f, fN = tempfile.mkstemp(suffix=".cnf", dir="/tmp", text="True")
        try:
            db = Db(optionFile=fN)
            db.connect()
        except DbException:
            pass
        # add socket only
        f = open(fN,'w')
        f.write('[client]\n')
        f.write('socket = /tmp/sth/wrong.sock\n')
        f.close()
        try:
            db = Db(optionFile=fN)
            db.connect()
        except DbException:
            pass
        os.remove(fN)

    def testIsConnected(self):
        """
        Test isConnected and isConnectedToDb.
        """
        db = Db(self._user, self._pass, socket=self._sock)
        db.disconnect()
        # not connected at all
        self.assertFalse(db.isConnected())
        # just initialize state, still not connected at all
        db = Db(self._user, self._pass, self._host, self._port, self._sock)
        self.assertFalse(db.isConnected())
        # connect to server, not to db
        db.connect()
        self.assertTrue(db.isConnected())
        # create db, still don't connect to it
        db.createDb(self._dbA)
        self.assertTrue(db.isConnected())
        self.assertNotEqual(db.getCurrentDbName(), self._dbA)
        self.assertNotEqual(db.getCurrentDbName(), self._dbB)
        # finally connect to it
        db.useDb(self._dbA)
        self.assertTrue(db.isConnected())
        self.assertEqual(db.getCurrentDbName(), self._dbA)
        self.assertNotEqual(db.getCurrentDbName(), self._dbB)
        # delete that database
        db.dropDb(self._dbA)

    def testMultiDbs(self):
        """
        Try interleaving operations on multiple databases.
        """
        db = Db(self._user, self._pass, self._host, self._port, self._sock)
        db.createDb(self._dbA)
        db.createDb(self._dbB)
        db.createDb(self._dbC)
        db.useDb(self._dbA)
        db.createTable("t1", "(i int)", self._dbB)
        db.createTable("t1", "(i int)")
        db.createTable("t1", "(i int)", self._dbC)
        db.dropDb(self._dbB)
        db.createTable("t2", "(i int)", self._dbA)
        db.dropDb(self._dbA)
        db.useDb(self._dbC)
        db.createTable("t2", "(i int)")
        db.createTable("t3", "(i int)", self._dbC)
        db.dropDb(self._dbC)
        db.disconnect()

    def testMultiCreateDef(self):
        """
        Test creating db/table that already exists (in default db).
        """
        db = Db(self._user, self._pass, self._host, self._port, self._sock)
        db.createDb(self._dbA)
        db.createDb(self._dbA, mayExist=True)
        self.assertRaises(DbException, db.createDb, self._dbA)
        db.useDb(self._dbA)
        self.assertRaises(DbException, db.createDb, self._dbA)
        db.createTable("t1", "(i int)")
        self.assertRaises(DbException, db.createTable, "t1", "(i int)")
        db.dropDb(self._dbA)

    def testDropDb(self):
        db = Db(self._user, self._pass, self._host, self._port, self._sock)
        db.createDb(self._dbA)
        db.dropDb(self._dbA)
        db.dropDb(self._dbA, mustExist=False)
        self.assertRaises(DbException, db.dropDb, self._dbA)
        db.disconnect()

    def testMultiCreateNonDef(self):
        """
        Test creating db/table that already exists (in non default db).
        """
        db = Db(self._user, self._pass, self._host, self._port, self._sock)
        db.createDb(self._dbA)
        self.assertRaises(DbException, db.createDb, self._dbA)
        db.useDb(self._dbA)
        db.createDb(self._dbB)
        self.assertRaises(DbException, db.createDb, self._dbA)
        db.createTable("t1", "(i int)")
        self.assertRaises(DbException, db.createTable, "t1", "(i int)")
        db.createTable("t2", "(i int)", self._dbA)
        self.assertRaises(DbException, db.createTable, "t1", "(i int)", self._dbA)
        self.assertRaises(DbException, db.createTable, "t2", "(i int)", self._dbA)

        db.createTable("t1", "(i int)", self._dbB)
        db.createTable("t1", "(i int)", self._dbB, mayExist=True)
        self.assertRaises(DbException, db.createTable, "t1", "(i int)", self._dbB)
        db.dropDb(self._dbA)
        db.disconnect()

    def testDropTable(self):
        db = Db(self._user, self._pass, self._host, self._port, self._sock)

        # using current db
        db.createDb(self._dbA)
        db.useDb(self._dbA)
        db.createTable("t2", "(i int)")
        db.dropTable("t2")
        db.dropTable("t2", mustExist=False)
        self.assertRaises(DbException, db.dropTable, "t2")
        db.dropDb(self._dbA)

        # using no current db
        db.createDb(self._dbB)
        db.createTable("t2", "(i int)", self._dbB)
        db.dropTable("t2", dbName=self._dbB)
        db.dropTable("t2", dbName=self._dbB, mustExist=False)
        self.assertRaises(DbException, db.dropTable, "t2", self._dbB)
        db.dropDb(self._dbB)

        # mix of current and not current db
        db.createDb(self._dbA)
        db.createDb(self._dbB)
        db.useDb(self._dbA)
        db.createTable("t2", "(i int)", self._dbB)
        db.createTable("t2", "(i int)")

        db.dropTable("t2")
        db.dropTable("t2", dbName=self._dbB)
        db.dropTable("t2", mustExist=False)
        db.dropTable("t2", dbName=self._dbB, mustExist=False)

        self.assertRaises(DbException, db.dropTable, "t2")
        self.assertRaises(DbException, db.dropTable, "t2", self._dbB)
        db.dropDb(self._dbA)
        db.dropDb(self._dbB)

        db.disconnect()

    def testCheckExists(self):
        """
        Test checkExist for databases and tables.
        """
        db = Db(self._user, self._pass, self._host, self._port, self._sock)
        self.assertFalse(db.dbExists("bla"))
        self.assertFalse(db.tableExists("bla"))
        self.assertFalse(db.tableExists("bla", "blaBla"))

        db.createDb(self._dbA)
        self.assertTrue(db.dbExists(self._dbA))
        self.assertFalse(db.dbExists("bla"))
        self.assertFalse(db.tableExists("bla"))
        self.assertFalse(db.tableExists("bla", "blaBla"))

        db.createTable("t1", "(i int)", self._dbA)
        self.assertTrue(db.dbExists(self._dbA))
        self.assertFalse(db.dbExists("bla"))
        self.assertTrue(db.tableExists("t1", self._dbA))
        db.useDb(self._dbA)
        self.assertTrue(db.tableExists("t1"))
        self.assertFalse(db.tableExists("bla"))
        self.assertFalse(db.tableExists("bla", "blaBla"))
        db.dropDb(self._dbA)

        self.assertFalse(db.userExists("d_Xx_u12my", "localhost"))
        self.assertTrue(db.userExists("root", "localhost"))

        db.disconnect()

    def testViews(self):
        """
        Testing functionality related to views.
        """
        db = Db(self._user, self._pass, self._host, self._port, self._sock)
        db.createDb(self._dbA)
        db.useDb(self._dbA)
        db.createTable("t1", "(i int, j int)")
        db.execCommand0("CREATE VIEW t2 AS SELECT i FROM t1")
        self.assertFalse(db.isView("t1"))
        self.assertTrue(db.isView("t2"))
        db.dropDb(self._dbA)

    def testServerRestart(self):
        """
        Testing recovery from lost connection.
        """
        db = Db(self._user, self._pass, self._host, self._port, self._sock,
                sleepLen=5, maxRetryCount=10)
        db.connect()
        db.createDb(self._dbA)
        #time.sleep(10)
        db.createDb(self._dbB)
        db.dropDb(self._dbA)
        db.dropDb(self._dbB)

    def testLoadSqlScriptNoDb(self):
        f, fN = tempfile.mkstemp(suffix=".csv", dir="/tmp", text="True")
        f = open(fN,'w')
        f.write("create database %s;\n" % self._dbA)
        f.write("use %s;\n" % self._dbA)
        f.write("create table t(i int);\n")
        f.write("insert into t values (1), (2), (2), (5);\n")
        f.close()
        db = Db(self._user, self._pass, self._host, self._port)
        db.loadSqlScript(fN)
        assert(10 == db.execCommand1("select sum(i) from %s.t" % self._dbA)[0])
        db.dropDb(self._dbA)
        db.disconnect()
        os.remove(fN)

    def testLoadSqlScriptWithDb(self):
        f, fN = tempfile.mkstemp(suffix=".csv", dir="/tmp", text="True")
        f = open(fN,'w')
        f.write("create table t(i int, d double);\n")
        f.write("insert into t values (1, 1.1), (2, 2.2);\n")
        f.close()
        db = Db(self._user, self._pass, self._host, self._port)
        db.createDb(self._dbA)
        db.loadSqlScript(fN, self._dbA)
        assert(3 == db.execCommand1("select sum(i) from %s.t" % self._dbA)[0])
        db.dropDb(self._dbA)
        db.disconnect()
        os.remove(fN)

    def testLoadDataInFile(self):
        """
        Testing "LOAD DATA INFILE..."
        """
        f, fN = tempfile.mkstemp(suffix=".csv", dir="/tmp", text="True")
        f = open(fN,'w')
        f.write('1\n2\n3\n4\n4\n4\n5\n3\n')
        f.close()

        db = Db(self._user, self._pass, socket=self._sock, local_infile=1)
        db.createDb(self._dbA)
        db.useDb(self._dbA)
        db.createTable("t1", "(i int)")
        db.execCommand0("LOAD DATA LOCAL INFILE '%s' INTO TABLE t1" % fN)
        x =  db.execCommand1("SELECT COUNT(*) FROM t1")
        assert(8 == db.execCommand1("SELECT COUNT(*) FROM t1")[0])
        assert(3 == db.execCommand1("SELECT COUNT(*) FROM t1 WHERE i=4")[0])

        # let's add some confusing data to the loaded file, it will get truncated
        f = open(fN,'w')
        f.write('11,12,13,14\n2')
        f.close()
        try:
            db.execCommand0("LOAD DATA LOCAL INFILE '%s' INTO TABLE t1" % fN)
        except DbException as e:
            print "Caught: #%s" % e.errCode, e
            assert(e.errCode == DbException.SERVER_WARNING)

        db.dropDb(self._dbA)
        db.disconnect()
        os.remove(fN)

####################################################################################
def main():
    logging.basicConfig(
        format='%(asctime)s %(name)s %(levelname)s: %(message)s', 
        datefmt='%m/%d/%Y %I:%M:%S', 
        level=logging.DEBUG)

    #try:
    unittest.main()
    #except DbException as e:
    #    print e

if __name__ == "__main__":
    main()
