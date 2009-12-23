package autotest.tko;

public abstract class AttributeField extends ParameterizedField {
    @Override
    public String getSqlCondition(String value) {
        return getSimpleSqlCondition(getQuotedSqlName() + ".value", value);
    }
}
