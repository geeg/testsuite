#!/usr/bin/env python
"""The Entrance of generation of test case spec xml.

Parse the root tag <test_suites>
"""
import glob, sys, os
sys.path.append("../")
from utility import file_path, test_config, analytics_tool
from utility.xml_parser import Parser
from executor.template_executor import ExecutorSpec
import dataset, multi_testsuite, para_handler 
import traceback

Path = file_path.Path()

class Generator (Parser):
    """Test case gnerator."""
    def __init__(self, configer, analyticsTools, datasets, specXml, 
                 caseScheduleFileHd, caseSQLFileHd, tsSqlFileHd, tiSqlFileHd):
        """
        params: 
            configer: configer class from test_config
            analyticsTools: all alalyticsTool info map
            datasets: dataset class to parse dataset xml
            specXml: test case spec xml file
            caseScheduleFileHd: test case schedule file descriptor
            caseSQLFileHd: test case sql out file descriptor
            tsSqlFileHd: sql file of inserting test suite, as tsSqlF in __init__'s para
            tiSqlFileHd: sql file of inserting test case, as tiSqlF in __init__'s para        
        """
        Parser.__init__(self, specXml)
        self.configer           =   configer
        self.analyticsTools     =   analyticsTools
        self.datasets           =   datasets
        self.paraHandler        =   para_handler.ParaHandler(analyticsTools, datasets)
        self.caseScheduleFileHd =   open(caseScheduleFileHd, "w")
        self.caseSQLFileHd      =   open(caseSQLFileHd, "w")
        self.testSuiteSqlHd     =   open(tsSqlFileHd, "w")
        self.testItemSqlHd      =   open(tiSqlFileHd, "w")

    def GenCases(self, debug = False):
        """Generate cases for each test case xml spec file

        Parse the root tag <test_suites>. 
        <test_type> has two options: feature and performance. For performance test, 
        each test case should be wraped by gpstart and gpstop
        output:
            1) one case schedule file which include gpstart/gpstop and test case file name,
               as caseScheduleF in __init__'s para
            2) multiply test case file with executor commands
            3) one sql output file, as caseSQLF in __init__'s para
            4) one sql file of inserting test suite, as tsSqlF in __init__'s para
            5) one sql file of inserting test case, as tiSqlF in __init__'s para
        """

        ts          =   Parser.getNodeTag(self, self.xmlDoc, "test_suites")
        tsType      =   Parser.getNodeVal(self, ts, "test_type")
        mulTsList   =   Parser.getNodeList(self, ts, "multi_test_suites")
        # loop to parse each multi test suite
        for mulTs in mulTsList:
            self.__multiTestSuite(mulTs, tsType, debug)

    def __multiTestSuite(self, mlTs, tsType, debug):
        """Parse one multi-test suite.

        params:
            mlTs: multi-test suite node
            tsType: <test_type>
        """

        algorithm   =   Parser.getNodeVal(self, mlTs, "algorithm")
        # parse pre parameters (hash table)
        methods     =   Parser.getNodeTag(self, mlTs, "methods")
        mtdNodeList =   Parser.getNodeList(self, methods, "method")
        preParas    =   self.__preParas(mtdNodeList)
        # get test suite nodes list
        tsNodeList  =   Parser.getNodeList(self, mlTs, "test_suite")
        # init a MutiTestSuite instance
        mlTs        =   multi_testsuite.MultiTestSuite(self.configer, self.analyticsTools, \
                                      self.datasets, self.paraHandler, algorithm, preParas, \
                                      tsNodeList, tsType, self.caseScheduleFileHd, \
                                      self.caseSQLFileHd, self.testSuiteSqlHd, self.testItemSqlHd)
        mlTs.GenCases(debug)

    def __preParas(self, mtdNodeList):
        """Get prepared parameters.

        params: 
            mtdNodeList: method node list.
        return:
            preParameters Hash tablb, the table format.
        key:methodName, value : method's preParameters array (including parameter name)
        """

        preParas = {}
        for mtd in mtdNodeList:
            prePara = []
            mtdName = Parser.getNodeVal(self, mtd,"name")
            for para in Parser.getNodeList(self, mtd,"parameter"):
                pName = Parser.getNodeVal(self, para, "name")
                pVal = Parser.getNodeVal(self, para, "value")
                prePara.extend(self.paraHandler.handle(pName, pVal, "pre", mtdName))
            preParas[mtdName] = prePara
        return preParas


def main():
    #remove old cases
    os.system('rm -rf ' + Path.TestCaseDir)
    os.system('mkdir ' + Path.TestCaseDir)

    debug = False
    if len(sys.argv) > 1 and sys.argv[1] == 'debug':
        debug = True

    try:
        # parse testconfig
        configer = test_config.Configer(Path.CfgSpecPath + Path.testconfigXml)
        configer.testconfig()
    except Exception, exp:
        print exp
        print "Error when parsing testconfig"
        sys.exit()

    try:
        # parse analyticsTool, generate "insert into " statement
        tbName = Path.analyticstoolXml.split(".")[0]
        analyticsTools = analytics_tool.AnalyticsTools(Path.CfgSpecPath + Path.analyticstoolXml)
        analyticsTools.parseTools()
        analyticsTools.generateSqlCmdfile(configer.resultDBSchema+"." + tbName, \
            Path.BootstrapDir + tbName + ".sql", Path.TestCaseDir + "init.cmd")
    except Exception, exp:
        print exp
        print "Error when parsing analyticsTools"
        sys.exit()

    try:
        # parse algorithm specification file, which is used by TemplateExecutor for madlib
        # generate "create table schema.algorithmname" statement
        spec = ExecutorSpec(Path.CfgSpecPath + Path.algorithmsSpecXml, configer.resultDBSchema)
        specName = Path.algorithmsSpecXml.split(".")[0]
        spec.writeCreateSQL(Path.BootstrapDir + specName + ".sql")

    except Exception, exp:
        print exp
        print "Error when parsing algorithm"
        sys.exit()

    try:
        # parse dataset
        datasets = dataset.Datasets(Path.CfgSpecPath + Path.datasetXml)
        datasets.getDataSets()
    except Exception, exp:
        print exp
        print "Error when parsing dataset"
        sys.exit()

    # generate test cases according to each spec xml file
    for specXml in glob.glob(Path.caseSpecPath + "*.xml"):
        # test case spec xml file name
        name = specXml.split("/")[len(specXml.split("/"))-1].split(".")[0]

        # test cases's file absolute path
        scheduleFile    =   Path.TestCaseDir + "case_" + name
        caseSQLFile     =   Path.TestCaseDir + name + ".sql_out"
        suiteSqlFile    =   Path.TestCaseDir + name + "suite.sql"
        itemSqlFile     =   Path.TestCaseDir + name + "item.sql"

        try:
            # create a generator to generate cases with this specXml
            generator = Generator(configer, analyticsTools. analyticsTools, datasets.descs, \
                specXml, scheduleFile, caseSQLFile, suiteSqlFile, itemSqlFile)
            generator.GenCases(debug)
        except Exception, exp:
            print traceback.format_exc()
            print exp
            print 'Error when generating ' +  name + "'s cases !"

if __name__ == '__main__':
    main()
