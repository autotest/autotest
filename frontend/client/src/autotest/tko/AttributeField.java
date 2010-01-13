package autotest.tko;

public abstract class AttributeField extends ParameterizedField {
    @Override
    public String getSqlCondition(String value) {
        return getSimpleSqlCondition(getFilteringName(), value);
    }

    @Override
    public String getFilteringName() {
        return getQuotedSqlName() + ".value";
    }
}
