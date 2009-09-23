package autotest.tko;

import java.util.Map;

import autotest.common.ui.MultiListSelectPresenter.Item;

public abstract class ParameterizedField extends HeaderField {
    private static final ParameterizedField[] prototypes = new ParameterizedField[] {
        // add all ParameterizedField subclasses here.  these instances should never escape. 
        new MachineLabelField(),
        new IterationResultField(),
    };

    private int fieldNumber;

    protected ParameterizedField() {
        super("", "");
    }

    public static ParameterizedField fromName(String name) {
        ParameterizedField prototype = getPrototypeByName(name);
        ParameterizedField newField = prototype.freshInstance();
        newField.initializeFrom(name, prototype.getBaseName());
        return newField;
    }

    public static ParameterizedField fromSqlName(String name) {
        ParameterizedField prototype = getPrototypeBySqlName(name);
        ParameterizedField newField = prototype.freshInstance();
        newField.initializeFrom(name, prototype.getBaseSqlName());
        return newField;
    }

    private static ParameterizedField getPrototype(String name, boolean isSqlName) {
        for (ParameterizedField prototype : prototypes) {
            String base;
            if (isSqlName) {
                base = prototype.getBaseSqlName();
            } else {
                base = prototype.getBaseName();
            }
            if (name.startsWith(base)) {
                return prototype;
            }
        }
        
        throw new IllegalArgumentException("No prototype found for " + name);
    }

    private static ParameterizedField getPrototypeByName(String name) {
        return getPrototype(name, false);
    }

    private static ParameterizedField getPrototypeBySqlName(String sqlName) {
        return getPrototype(sqlName, true);
    }

    private void initializeFrom(String name, String base) {
        assert name.startsWith(base);

        String numberString = name.substring(base.length()).trim();
        try {
            fieldNumber = Integer.valueOf(numberString);
        } catch (NumberFormatException exc) {
            throw new IllegalArgumentException("Failed to parse number for header " + name 
                                               + " (" + numberString + ")");
        }

        this.name = getBaseName() + " " + numberString;
        this.sqlName = getBaseSqlName() + numberString;
    }

    public int getFieldNumber() {
        return fieldNumber;
    }

    /**
     * Parameterized fields create generated items rather than regular items.
     */
    @Override
    public Item getItem() {
        return Item.createGeneratedItem(getName(), getSqlName());
    }

    public static Item getGenerator(String baseName) {
        ParameterizedField prototype = getPrototypeByName(baseName);
        return Item.createGenerator(prototype.getBaseName() + "...", prototype.getBaseSqlName());
    }

    @Override
    public void addHistoryArguments(Map<String, String> arguments) {
        arguments.put(getName(), getValue());
    }

    @Override
    public void handleHistoryArguments(Map<String, String> arguments) {
        assert arguments.containsKey(getName()) : getName();
        setValue(arguments.get(getName()));
    }

    public abstract String getBaseSqlName();
    protected abstract String getBaseName();

    public abstract String getValue();
    public abstract void setValue(String value);

    protected abstract ParameterizedField freshInstance();
}
