package autotest.tko;


class SimpleHeaderField extends HeaderField {
    public SimpleHeaderField(String name, String sqlName) {
        super(name, sqlName);
    }

    @Override
    public String getSqlCondition(String value) {
        return getSimpleSqlCondition(getQuotedSqlName(), value);
    }
}
