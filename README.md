# ef2

Updated R package for processing IRS 990 Efile datasets. 

This package is a Gen 2 version of the [irs990efile](https://github.com/Nonprofit-Open-Data-Collective/irs990efile) package with an improved XML to RDB workflow that is more robust and reduces processing time to about 15 minutes per tax year (the original package takes about 3 days to process one tax year). 

Pre-processed files are available on the NCCS website in CSV format: https://nccs.urban.org/nccs/datasets/efile/


## Process

### Step 1: Flatten XML Files 

Convert XML files to something the resembles a Parquet long format. Raw XML fields: 

```
<BooksInCareOfDetail>
  <PersonNm>Vanuel Bloss</PersonNm>
  <USAddress>
    <AddressLine1Txt>319 Linsbury Ct</AddressLine1Txt>
    <CityNm>Gastonia</CityNm>
    <StateAbbreviationCd>NC</StateAbbreviationCd>
    <ZIPCd>28056</ZIPCd>
  </USAddress>
  <PhoneNum>7048241662</PhoneNum>
</BooksInCareOfDetail>
```

Get converted into a table with one row per XML node. In other words, the file is flattened so that each piece of data (the VALUE column) gets a separate row. 


| XPATH                                             | NODE_TYPE | VARIABLE_NAME               | TABLE_NAME        | VALUE             |
|:------------------------------------------------- |:--------- |:--------------------------- |:----------------- |:----------------- |
| BooksInCareOfDetail                               | parent    |                             |                   |                   |
| BooksInCareOfDetail/PersonNm                      | terminal  | F9_P0_IN_CARE_OF_NAME       | F9-P00-T00-HEADER | Manuel Floss      |
| BooksInCareOfDetail/USAddress/AddressLine1Txt     | terminal  | F9_P0_IN_CARE_OF_ADDR_L1    | F9-P00-T00-HEADER | 319 Lingenbury Ct |
| BooksInCareOfDetail/USAddress/CityNm              | terminal  | F9_P0_IN_CARE_OF_ADDR_CITY  | F9-P00-T00-HEADER | Gastanio          |
| BooksInCareOfDetail/USAddress/StateAbbreviationCd | terminal  | F9_P0_IN_CARE_OF_ADDR_STATE | F9-P00-T00-HEADER | NC                |
| BooksInCareOfDetail/USAddress/ZIPCd               | terminal  | F9_P0_IN_CARE_OF_ADDR_ZIP   | F9-P00-T00-HEADER | 20056             |
| BooksInCareOfDetail/PhoneNum                      | terminal  | F9_P0_IN_CARE_OF_PHONE      | F9-P00-T00-HEADER | 8048241362        |

Note that some XML nodes are "parent" nodes whose only role is to group children nodes ("terminal" nodes) to provide the heirarchical structure that gives XML the flexibility to embed tables within tables. These nodes contain no data and filtered out before converting the flattened XML file into tables. 

Flattened XML files are stored as a DuckDB instance on an AWS S3 server. 

### Step 2: Extract Tables

The table structures and variable names are all defined within the [990 Concordance]() file. Once the XML conversions to flat files is complete, the data is transformed by pivoting each table to a "wide" format: 

**F9-P00-T00-HEADER TABLE**: 

| F9_P0_IN_CARE_OF_NAME | F9_P0_IN_CARE_OF_ADDR_L1 | F9_P0_IN_CARE_OF_ADDR_CITY | F9_P0_IN_CARE_OF_ADDR_STATE | F9_P0_IN_CARE_OF_ADDR_ZIP | F9_P0_IN_CARE_OF_PHONE |
| --------------------- | ------------------------ | -------------------------- | --------------------------- | ------------------------- | ---------------------- |
| Manuel Floss          | 319 Lingenbury Ct        | Gastanio                   | NC                          | 20056                     | 8048241362             |

### Additional Details 

All Efile tables contain a consistent set of metadata fields the describe both the organization (EIN, name), the type of filing (form type, tax year), and XML attributes (the original xpath, the URL of the raw file, the time stamp of return submission). 

In addition, they contain a set of filtering variables that are useful when preparing data for analysis - indicators of whether the filing in an amended return or a group return, and an indicator of whether it is a partial return. These fields are used for removing redundant files since 

## Code Tutorial 

### Step 1: Flatten XMLs

### Step 2: Attach an S3 DuckDB File 

### Step 3: Extract One-to-One Tables 

### Step 4: Extract One-to-Many Tables 






