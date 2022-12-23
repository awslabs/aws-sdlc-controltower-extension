**Error:**

```bash
AWS Control Tower cannot create an account because you have reached the limit on the number of accounts in your organization
```

**Solution:**

Increase the service limit for AWS Organizations "Default maximum number of accounts".

1. Search for "Service Quotas". 
![alt text](../images/errors/error1-1.png)

2. Select "AWS services" from the left pane.
![alt text](../images/errors/error1-2.png)

3. Search for "AWS Organizations".
![alt text](../images/errors/error1-3.png)

4. Select the "Default maximum number of accounts" ratio button, then click the "Request quota increase" button.
![alt text](../images/errors/error1-4.png)

5. Under "Change quota value" enter in the desired value, then click on "Request".
![alt text](../images/errors/error1-5.png) 



