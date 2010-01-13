package autotest.tko;

import autotest.common.Utils;

public abstract class LabelField extends ParameterizedField {
    @Override
    public String getSqlCondition(String value) {
        String condition = " IS NOT NULL";
        if (value.equals(Utils.JSON_NULL)) {
            condition = " IS NULL";
        }
        return getFilteringName() + condition;
    }

    @Override
    public String getFilteringName() {
        return getQuotedSqlName() + ".id";
    }
}
