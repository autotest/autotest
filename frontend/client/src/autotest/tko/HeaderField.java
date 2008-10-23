package autotest.tko;

import com.google.gwt.json.client.JSONObject;

abstract class HeaderField implements Comparable<HeaderField> {
    private String name;
    private String sqlName;
    
    protected HeaderField(String name, String sqlName) {
        this.name = name;
        this.sqlName = sqlName;
    }
    
    public int compareTo(HeaderField other) {
        return name.compareTo(other.name);
    }

    /**
     * Get the SQL WHERE clause to filter on the given value for this header.
     */
    public abstract String getSqlCondition(String value);
    
    /**
     * Get the name of this field.
     */
    public String getName() {
        return name;
    }
    
    /**
     * Get the name to use for this field in a SQL select.
     */
    public String getSqlName() {
        return sqlName;
    }
    
    /**
     * Add necessary parameters to an RPC request to select this field.
     */
    public abstract void addQueryParameters(JSONObject parameters);
}
