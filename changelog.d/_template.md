{% for section, _ in sections.items() %}
{% if sections[section] %}
{% for category, val in sections[section].items() %}
{% if val and category != 'misc' %}
### {{ definitions[category]['name'] or category }}

{% for text, values in val.items() %}
- {{ text }}
{% endfor %}

{% endif %}
{% endfor %}
{% else %}
No significant changes.

{% endif %}
{% endfor %}
