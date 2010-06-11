package autotest.tko;

import autotest.common.Utils;
import autotest.common.ui.MultiListSelectPresenter.Item;

import com.google.gwt.json.client.JSONObject;

/**
 * A field associated with test results.  The user may
 * * view this field in table view,
 * * sort by this field in table view,
 * * group by this field in spreadsheet or table view, and
 * * filter on this field in the SQL condition.
 * It's assumed that the name returned by getSqlName() is a field returned by the server which may
 * also be used for grouping and sorting.  Filtering, however, is done separately (through
 * getSqlCondition()), so HeaderFields may generate arbitrary SQL to perform filtering.
 * HeaderFields may also add arbitrary query arguments to support themselves.
 *
 * While the set of HeaderFields active in the application may change at runtime, HeaderField
 * objects themselves are immutable.
 */
public abstract class HeaderField implements Comparable<HeaderField> {
    protected String name;
    protected String sqlName;

    /**
     * @param name Display name for this field (i.e. "Job name")
     * @param sqlName SQL field name (i.e. "job_name")
     */
    protected HeaderField(String name, String sqlName) {
        this.name = name;
        this.sqlName = sqlName;
    }

    public int compareTo(HeaderField other) {
        return name.compareTo(other.name);
    }

    /**
     * A common helper for SQL conditions.
     */
    protected String getSimpleSqlCondition(String field, String value) {
        if (value.equals(Utils.JSON_NULL)) {
          return field + " is null";
        } else {
          return field + " = '" + TkoUtils.escapeSqlValue(value) + "'";
        }
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
     * Get a quoted version of getSqlName() safe for use directly in SQL.
     */
    public String getQuotedSqlName() {
        String sqlName = getSqlName();
        if (sqlName.matches(".+\\(.+\\)")) {
            // don't quote fields involving SQL functions
            return sqlName;
        }
        return "`" + sqlName + "`";
    }

    @Override
    public String toString() {
        return "HeaderField<" + getName() + ", " + getSqlName() + ">";
    }

    /**
     * Should this field be provided as a choice for the user to select?
     */
    public boolean isUserSelectable() {
        return true;
    }

    /**
     * @return a MultiListSelectPresenter.Item for this HeaderField.
     */
    public Item getItem() {
        return Item.createItem(getName(), getSqlName());
    }

    /**
     * Add necessary parameters to an RPC request to select this field.  Does nothing by default.
     * @param parameters query parameters
     */
    public void addQueryParameters(JSONObject parameters) {}
}
