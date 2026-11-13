package com.duivesteyn.papir.core

/**
 * Values produced by the Python reference implementation
 * (`papir/signer.py`, `papir/papir.py`). Do not hand-edit: regenerate with
 * `python3 android/tools/make-fixtures.py`.
 */
object Fixtures {
    const val ADP_TOKEN = "AMP-test-adp-token"
    const val DATE = "2026-01-02T03:04:05Z"
    const val PATH = "/GetUploadUrl"
    const val METHOD = "POST"
    const val BODY = """{"ClientInfo":{"appName":"ShellExtension","appVersion":"1.1.1.253","os":"MacOSX_10.14.6_x64","osArchitecture":"x64"},"fileSize":123456}"""

    const val EXPECTED_DIGEST = "TvXyuuAQ4f2KBjHhp6M8WIOTD+bwRf+K16M4EbzsXwz+EImJmjqvGQGvzmLyb5n/XmwClrDaAbBejfJjYPGUE6asNolxi/Zq4HzqtLpwQg+qhqtbmmsg+FWYNZ/OBoFLLeJdavtsURKq9WAJVXGnIYV0YEU4n7TIFZgWVlr5nAZpfMUpRLvkcc626mLqsX+1PPnAq6TFR4mpb7kcU1Arjps1FGoULi4yIkGgtI7X6UJqrOIgJyv/dybp5NNh2ORwTR/sam48RXFFnVhITsstCZvJ2GUc1btuwZ4cKBV36hPjalTPHUT0uLFXyCOeAOU7mncu/X67gItAWatmiP0ArA==:2026-01-02T03:04:05Z"

    const val VERIFIER = "test-verifier-1234567890abcdefghijklmnopqrstuvwxyz"
    const val EXPECTED_CHALLENGE = "L3wfP7dX3v7URt0-GZkAepH0XAV8ghg9T0l8LFrH3L8"

    val PKCS1_KEY: String = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAykMbZvwVkw8JsuISQLYK2SZRBeBPbZoIDGGgAQJ0MgkC/hOC
5W0HbExdFtqFy3SVP2lW1sGf6USB85e5qoArh5NZnlP9p9BmtlyMOJK3D8TcFTdt
wkPhH2xKPih5bekhFD5qcGAp4XSclfpW1zjzQ8ltnQWcrON7N1hXguSdsZ7AONId
ifKNslAfK+OV5Mm84pRg94nnLwYUROHXvxWDjgrY0oi2hgiCLfivIp5MpIhUI+FY
ye1x0cWSnxGQd0HdxPEUo2txk3mF4joq6NSZeLuQv6sYnMbG32XYj0SD5dJZCoES
S3/E+sS9mtXOF72gOjju8b0DnIb/TDFEBhCA7wIDAQABAoIBAQCCqWFtYRIK418P
mW3TMgbGCzOySRrmoefrH7H+lPg9TocJXc9kqM9vzdEhL1/ZdGHqCgHYUFMenWwZ
0f1WQOBd//mYB4hIvZ9s1VKcRWNPI4xNhHY6ViF7bDh1+S2grEb7Tery15yWkf+J
/6PT+21jcB+InZR+N6JkuYQnActBbzecOAdgORRH9f1lsCtSh1K2RfOYQzJ8ett3
5mp7e7jADrESjwUkFPVZOpD22yD6mI2GVtQZFtKxxlN6vD3nJZTXu2ycg7AqB/Ii
yXOZ1ROdP9it4j0RjJw9b/5IZw9P61DcRLlGBJnBk+Jnzkxg5LN9eBUyMkIe3cpH
+U44V0BxAoGBAOOhIZksNWiN+7pyZsCXgmiB46eHqSooIwDkgyBSxilxjipjcUn4
h1tAsxeg7RE03C2C10Hvo+roM0UhcFnmOjJltgCfpunHkiiR4zl9zzXuUS6GOzEf
o2mRwmDEZJP5Iafrx4HDnR5YQdlLAKENUh+jnBsMoJHmkA/8h6L+qsrXAoGBAON4
l+pXs5N8/0P7x8tZzbRUWdukW88N21edepVhcuY1hhn0iTgVsbXuPvH/0HJDdKQq
aaewtd+aISrCDNEVAkBqa/CNEybgFLzzS5EaqwrF2h8YZfnPyWJuPClSYTMdqKas
fiPiiFIA+zvYlk6cZj1E5+ZXgZqZFHdSTS32Qg+pAoGAXQSycyJyrMggjv9C5/7B
5qz1d7djNHv0WeAHiYTpv3PM8ZtzZxPtVCfrR4OWfMqKEvr9tc8Uv+ClWuGgRMxl
CcUwi66yCaRpILUFErBLpbE+cXGe7KMOJwzOTrbSlvlefH1IKMnkAct1FTOmDSoh
XhaAqzkMwLJkOnQqhTvmVT8CgYEAyVa8YFgwQqOo7eu19HAQe0UOJDNeb+677tkc
34vZv5owkFi5/EJ3gajXXiwnvHuoioZf7mWjFb+/C7Gm1onZ7FpGIC0+fnJo6LYQ
dOc97dMiNdPKr0sT3WPlLE4WasAdvyl+nRStxKfJuDcFE5+rfx+2g1OBC+3jB5p5
Ze1Km8ECgYBM1YdGTU74XqcX2dWozu6n2o78MlnhUqZlkVW0IJj+jHkI2563RoDm
ldgWJJvqBpijCD0ynam9WTW+zsz5XqGv1m20BMSybZbrkOsOx68+gOWmfOYY8PO+
C2x6IqxnoTTUIZExUCLqaezP7p2O1yvSAeI6Lik8Cu28zPGoi16B+w==
-----END RSA PRIVATE KEY-----"""
    val PKCS8_KEY: String = """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDKQxtm/BWTDwmy
4hJAtgrZJlEF4E9tmggMYaABAnQyCQL+E4LlbQdsTF0W2oXLdJU/aVbWwZ/pRIHz
l7mqgCuHk1meU/2n0Ga2XIw4krcPxNwVN23CQ+EfbEo+KHlt6SEUPmpwYCnhdJyV
+lbXOPNDyW2dBZys43s3WFeC5J2xnsA40h2J8o2yUB8r45XkybzilGD3iecvBhRE
4de/FYOOCtjSiLaGCIIt+K8inkykiFQj4VjJ7XHRxZKfEZB3Qd3E8RSja3GTeYXi
Oiro1Jl4u5C/qxicxsbfZdiPRIPl0lkKgRJLf8T6xL2a1c4XvaA6OO7xvQOchv9M
MUQGEIDvAgMBAAECggEBAIKpYW1hEgrjXw+ZbdMyBsYLM7JJGuah5+sfsf6U+D1O
hwldz2Soz2/N0SEvX9l0YeoKAdhQUx6dbBnR/VZA4F3/+ZgHiEi9n2zVUpxFY08j
jE2EdjpWIXtsOHX5LaCsRvtN6vLXnJaR/4n/o9P7bWNwH4idlH43omS5hCcBy0Fv
N5w4B2A5FEf1/WWwK1KHUrZF85hDMnx623fmant7uMAOsRKPBSQU9Vk6kPbbIPqY
jYZW1BkW0rHGU3q8PecllNe7bJyDsCoH8iLJc5nVE50/2K3iPRGMnD1v/khnD0/r
UNxEuUYEmcGT4mfOTGDks314FTIyQh7dykf5TjhXQHECgYEA46EhmSw1aI37unJm
wJeCaIHjp4epKigjAOSDIFLGKXGOKmNxSfiHW0CzF6DtETTcLYLXQe+j6ugzRSFw
WeY6MmW2AJ+m6ceSKJHjOX3PNe5RLoY7MR+jaZHCYMRkk/khp+vHgcOdHlhB2UsA
oQ1SH6OcGwygkeaQD/yHov6qytcCgYEA43iX6lezk3z/Q/vHy1nNtFRZ26Rbzw3b
V516lWFy5jWGGfSJOBWxte4+8f/QckN0pCppp7C135ohKsIM0RUCQGpr8I0TJuAU
vPNLkRqrCsXaHxhl+c/JYm48KVJhMx2opqx+I+KIUgD7O9iWTpxmPUTn5leBmpkU
d1JNLfZCD6kCgYBdBLJzInKsyCCO/0Ln/sHmrPV3t2M0e/RZ4AeJhOm/c8zxm3Nn
E+1UJ+tHg5Z8yooS+v21zxS/4KVa4aBEzGUJxTCLrrIJpGkgtQUSsEulsT5xcZ7s
ow4nDM5OttKW+V58fUgoyeQBy3UVM6YNKiFeFoCrOQzAsmQ6dCqFO+ZVPwKBgQDJ
VrxgWDBCo6jt67X0cBB7RQ4kM15v7rvu2Rzfi9m/mjCQWLn8QneBqNdeLCe8e6iK
hl/uZaMVv78LsabWidnsWkYgLT5+cmjothB05z3t0yI108qvSxPdY+UsThZqwB2/
KX6dFK3Ep8m4NwUTn6t/H7aDU4EL7eMHmnll7UqbwQKBgEzVh0ZNTvhepxfZ1ajO
7qfajvwyWeFSpmWRVbQgmP6MeQjbnrdGgOaV2BYkm+oGmKMIPTKdqb1ZNb7OzPle
oa/WbbQExLJtluuQ6w7Hrz6A5aZ85hjw874LbHoirGehNNQhkTFQIupp7M/unY7X
K9IB4jouKTwK7bzM8aiLXoH7
-----END PRIVATE KEY-----"""

    val TITLES: Map<String, String> = mapOf(
        "Light_and_Wonder_LNW_Investment_Report_v1.2_2026-10-06" to "Light and Wonder LNW Investment Report",
        "report" to "report",
        "2026-10-06" to "2026-10-06",
        "Quarterly Report 2026-03-31" to "Quarterly Report",
        "Design Systems v2.1" to "Design Systems",
        "budget_final_v3" to "budget final",
        "a b  c" to "a b c",
        "paper" to "paper",
    )
}
